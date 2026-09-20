import hashlib, json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.core.errors import AppError
from app.models.campaigns import PolicySetting, ValidationRun, ValidationRecipient, Approval
from app.repositories import policies as repository
from app.repositories.analytics import customer_snapshot
from app.repositories.imports import data_version
from app.domain.segments.dsl import Condition
from app.domain.segments.compiler import expressions, compile_condition
from app.domain.policies.rules import ordered_reasons, rule_results, REASON_ORDER
from app.services.datasets import require_dataset
from app.services.audit import record_change
from app.services.campaigns import representation
from app.repositories import campaigns as campaigns_repository

CHANNELS=('EMAIL','PUSH','SMS')
DEFAULT_FORBIDDEN={channel:['무조건 당첨'] for channel in CHANNELS}
DEFAULT_REQUIRED={channel:[] for channel in CHANNELS}

def policy_repr(row,dataset_id):
    return {'dataset_id':dataset_id,'version':row.version if row else 1,'daily_limit':row.daily_limit if row else 1,
        'weekly_limit':row.weekly_limit if row else 3,'forbidden_phrases':row.forbidden_phrases if row else DEFAULT_FORBIDDEN,
        'required_phrases':row.required_phrases if row else DEFAULT_REQUIRED}

def get_policy(session,dataset_id):
    require_dataset(session,dataset_id)
    return policy_repr(repository.setting(session,dataset_id),dataset_id)

def update_policy(session,payload,request_id):
    with session.begin():
        require_dataset(session,payload.dataset_id,lock=True)
        row=repository.setting(session,payload.dataset_id,True)
        current=row.version if row else 1
        if payload.version!=current: raise AppError('VERSION_CONFLICT','정책이 변경되었습니다. 최신 설정을 불러오세요.')
        if row is None:
            row=PolicySetting(dataset_id=payload.dataset_id,version=2); session.add(row)
        else: row.version+=1
        row.daily_limit=payload.daily_limit; row.weekly_limit=payload.weekly_limit
        row.forbidden_phrases=payload.forbidden_phrases; row.required_phrases=payload.required_phrases
        session.flush(); record_change(session,dataset_id=payload.dataset_id,resource_id=row.id,actor_type='VISITOR',action='POLICY_UPDATED',request_id=request_id,previous_version=current if current else None,new_version=row.version)
        return policy_repr(row,payload.dataset_id)

def campaign_hash(session,campaign):
    value=representation(session,campaign)
    stable={key:value[key] for key in ('id','segment_revision_id','exclusion_revision_ids','channel','benefit','coupon_expires_at','variants')}
    return hashlib.sha256(json.dumps(stable,sort_keys=True,separators=(',',':'),default=str,ensure_ascii=False).encode()).hexdigest()

def validation_repr(row):
    return {'id':row.id,'dataset_id':row.dataset_id,'campaign_id':row.campaign_id,'campaign_version':row.campaign_version,
        'policy_version':row.policy_version,'data_version':row.data_version,'reference_at':row.reference_at,'content_hash':row.content_hash,
        'initial_count':row.initial_count,'eligible_count':row.eligible_count,'excluded_count':row.excluded_count,
        'passed':row.passed,'rules':row.rules,'blockers':row.blockers,'expires_at':row.expires_at,'created_at':row.created_at}

def approval_repr(row):
    return None if row is None else {'id':row.id,'dataset_id':row.dataset_id,'campaign_id':row.campaign_id,'validation_run_id':row.validation_run_id,
        'campaign_version':row.campaign_version,'status':row.status,'decision_source':row.decision_source,'comment':row.comment,'decided_at':row.decided_at,'created_at':row.created_at}

def review(session,dataset_id,campaign_id):
    campaign=campaigns_repository.get(session,dataset_id,campaign_id)
    if campaign is None: raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
    validation=repository.latest_validation(session,dataset_id,campaign_id); approval=repository.latest_approval(session,dataset_id,campaign_id)
    return {'campaign':representation(session,campaign),'validation':validation_repr(validation) if validation else None,'approval':approval_repr(approval)}

def validate(session,campaign_id,payload,request_id,*,actor_type='VISITOR'):
    with session.begin():
        require_dataset(session,payload.dataset_id,lock=True)
        campaign=campaigns_repository.get(session,payload.dataset_id,campaign_id,True)
        if campaign is None: raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
        if campaign.status!='DRAFT' or campaign.version!=payload.campaign_version: raise AppError('VERSION_CONFLICT','작성 중인 최신 캠페인만 검수할 수 있습니다.')
        policy=policy_repr(repository.setting(session,payload.dataset_id),payload.dataset_id)
        version=data_version(session,payload.dataset_id)
        revision=repository.revision(session,payload.dataset_id,campaign.segment_revision_id)
        snapshot=customer_snapshot(payload.dataset_id,payload.reference_at); fields=expressions(snapshot,payload.dataset_id,payload.reference_at)
        ids=list(session.scalars(select(snapshot.c.id).where(compile_condition(Condition.model_validate(revision.condition_json),fields))))
        excluded=set()
        for item in repository.exclusion_revisions(session,campaign.id):
            excluded.update(session.scalars(select(snapshot.c.id).where(compile_condition(Condition.model_validate(item.condition_json),fields))))
        channels=repository.channels(session,payload.dataset_id,ids,campaign.channel)
        statuses=dict(session.execute(select(snapshot.c.id,snapshot.c.status).where(snapshot.c.id.in_(ids))).all()) if ids else {}
        zone=ZoneInfo('Asia/Seoul'); local=payload.reference_at.astimezone(zone)
        day_start=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
        counts=repository.delivery_counts(session,payload.dataset_id,ids,campaign.channel,campaign.id,day_start,payload.reference_at-timedelta(days=7),payload.reference_at) if ids else {}
        recipients=[]; reason_counts={code:0 for code in REASON_ORDER}; primary_counts={code:0 for code in REASON_ORDER}
        for customer_id in ids:
            channel=channels.get(customer_id); duplicate,daily,weekly=counts.get(customer_id,(0,0,0))
            reasons=ordered_reasons(withdrawn=statuses.get(customer_id)=='WITHDRAWN',consent=bool(channel and channel.consent),
                contact=channel.contact if channel else None,valid=bool(channel and channel.is_valid),hard_bounce=bool(channel and channel.hard_bounce),
                excluded=customer_id in excluded,duplicate=duplicate>0,daily=daily,weekly=weekly,daily_limit=policy['daily_limit'],weekly_limit=policy['weekly_limit'])
            for code in reasons: reason_counts[code]+=1
            if reasons: primary_counts[reasons[0]]+=1
            recipients.append(ValidationRecipient(dataset_id=payload.dataset_id,customer_id=customer_id,eligible=not reasons,primary_reason=reasons[0] if reasons else None,reasons=reasons))
        eligible=sum(row.eligible for row in recipients); blockers=[]
        if campaign.coupon_expires_at and campaign.coupon_expires_at<=payload.reference_at: blockers.append({'rule_code':'EXPIRED_COUPON','message':'쿠폰 만료 시각이 검수 기준 시점보다 이전입니다.'})
        variants,_=campaigns_repository.children(session,campaign)
        forbidden=policy['forbidden_phrases'].get(campaign.channel,[]); required=policy['required_phrases'].get(campaign.channel,[])
        all_text='\n'.join(v.subject+'\n'+v.body for v in variants)
        for phrase in forbidden:
            if phrase in all_text: blockers.append({'rule_code':'FORBIDDEN_PHRASE','message':f'금지 표현이 포함되어 있습니다: {phrase}'})
        for phrase in required:
            if phrase not in all_text: blockers.append({'rule_code':'REQUIRED_PHRASE','message':f'필수 문구가 누락되었습니다: {phrase}'})
        if sum(v.allocation_bp for v in variants)!=10000: blockers.append({'rule_code':'INVALID_ALLOCATION','message':'A/B 비율 합계가 100%가 아닙니다.'})
        if eligible==0: blockers.append({'rule_code':'NO_ELIGIBLE_RECIPIENT','message':'발송 가능한 대상 고객이 없습니다.'})
        rules=rule_results(reason_counts)
        for row in rules: row['primary_count']=primary_counts[row['rule_code']]
        run=ValidationRun(dataset_id=payload.dataset_id,campaign_id=campaign.id,campaign_version=campaign.version,segment_revision_id=campaign.segment_revision_id,
            policy_version=policy['version'],data_version=version,reference_at=payload.reference_at,content_hash=campaign_hash(session,campaign),initial_count=len(ids),eligible_count=eligible,
            excluded_count=len(ids)-eligible,passed=not blockers,rules=rules,blockers=blockers,expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
        session.add(run); session.flush()
        for row in recipients: row.validation_run_id=run.id
        session.add_all(recipients)
        record_change(session,dataset_id=payload.dataset_id,resource_id=campaign.id,actor_type=actor_type,action='CAMPAIGN_VALIDATED',request_id=request_id,previous_version=campaign.version,new_version=campaign.version)
        return validation_repr(run)

def request_approval(session,campaign_id,payload,request_id):
    with session.begin():
        require_dataset(session,payload.dataset_id,lock=True); campaign=campaigns_repository.get(session,payload.dataset_id,campaign_id,True)
        if campaign is None: raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
        run=repository.get_validation(session,payload.dataset_id,payload.validation_run_id,True)
        policy=policy_repr(repository.setting(session,payload.dataset_id),payload.dataset_id)
        if campaign.status!='DRAFT' or campaign.version!=payload.campaign_version: raise AppError('VERSION_CONFLICT','캠페인 상태 또는 버전이 변경되었습니다.')
        if run is None or run.campaign_id!=campaign.id or not run.passed: raise AppError('VALIDATION_REQUIRED','통과한 최신 검수가 필요합니다.')
        now=datetime.now(timezone.utc)
        if run.expires_at<=now or run.campaign_version!=campaign.version or run.policy_version!=policy['version'] or run.data_version!=data_version(session,payload.dataset_id) or run.content_hash!=campaign_hash(session,campaign):
            raise AppError('VALIDATION_EXPIRED','검수 결과가 만료되었거나 기준 데이터가 변경되었습니다.')
        previous=campaign.version; campaign.status='REVIEW'; campaign.version+=1
        approval=Approval(dataset_id=payload.dataset_id,campaign_id=campaign.id,validation_run_id=run.id,campaign_version=campaign.version,status='PENDING')
        session.add(approval); session.flush(); record_change(session,dataset_id=payload.dataset_id,resource_id=campaign.id,actor_type='VISITOR',action='APPROVAL_REQUESTED',request_id=request_id,previous_version=previous,new_version=campaign.version)
        return {'campaign':representation(session,campaign),'approval':approval_repr(approval)}

def decide(session,campaign_id,payload,request_id,approved):
    with session.begin():
        require_dataset(session,payload.dataset_id,lock=True); campaign=campaigns_repository.get(session,payload.dataset_id,campaign_id,True)
        approval=repository.get_approval(session,payload.dataset_id,payload.approval_id,True)
        if campaign is None or approval is None or approval.campaign_id!=campaign.id: raise AppError('NOT_FOUND','승인 요청을 찾을 수 없습니다.',404)
        if campaign.status!='REVIEW' or campaign.version!=payload.campaign_version or approval.status!='PENDING' or approval.campaign_version!=campaign.version:
            raise AppError('VERSION_CONFLICT','이미 처리되었거나 캠페인 버전이 변경되었습니다.')
        run=repository.get_validation(session,payload.dataset_id,approval.validation_run_id)
        policy=policy_repr(repository.setting(session,payload.dataset_id),payload.dataset_id)
        if approved and (run.expires_at<=datetime.now(timezone.utc) or run.policy_version!=policy['version']
                         or run.data_version!=data_version(session,payload.dataset_id) or run.content_hash!=campaign_hash(session,campaign)):
            raise AppError('VALIDATION_EXPIRED','검수 결과가 만료되었거나 기준 데이터가 변경되었습니다.')
        previous=campaign.version; campaign.status='APPROVED' if approved else 'DRAFT'; campaign.version+=1
        approval.status='APPROVED' if approved else 'REJECTED'; approval.decision_source='VISITOR'; approval.comment=payload.comment; approval.decided_at=datetime.now(timezone.utc)
        record_change(session,dataset_id=payload.dataset_id,resource_id=campaign.id,actor_type='VISITOR',action='CAMPAIGN_APPROVED' if approved else 'CAMPAIGN_REJECTED',request_id=request_id,previous_version=previous,new_version=campaign.version)
        return {'campaign':representation(session,campaign),'approval':approval_repr(approval)}

def resume(session,campaign_id,payload,request_id):
    with session.begin():
        require_dataset(session,payload.dataset_id,lock=True); campaign=campaigns_repository.get(session,payload.dataset_id,campaign_id,True)
        if campaign is None: raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
        if campaign.status not in ('REVIEW','APPROVED') or campaign.version!=payload.campaign_version: raise AppError('VERSION_CONFLICT','편집을 재개할 수 없는 상태입니다.')
        approval=repository.latest_approval(session,payload.dataset_id,campaign.id)
        if approval and approval.status=='PENDING': approval.status='WITHDRAWN'; approval.decision_source='VISITOR'; approval.decided_at=datetime.now(timezone.utc)
        previous=campaign.version; campaign.status='DRAFT'; campaign.version+=1
        record_change(session,dataset_id=payload.dataset_id,resource_id=campaign.id,actor_type='VISITOR',action='CAMPAIGN_EDITING_RESUMED',request_id=request_id,previous_version=previous,new_version=campaign.version)
        return representation(session,campaign)
