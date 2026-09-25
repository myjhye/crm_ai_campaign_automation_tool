import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from app.core.errors import AppError
from app.models.campaigns import (CampaignRun, CampaignDelivery, CampaignEvent, CampaignVariant, ValidationRecipient)
from app.models.customers import Customer, Order
from app.repositories import campaigns as campaign_repo, policies as policy_repo
from app.repositories.imports import data_version
from app.domain.policies.rules import ordered_reasons
from app.services.datasets import require_dataset
from app.services.jobs import enqueue
from app.services.audit import record_change
from app.services.policies import policy_repr, campaign_hash

RATES={'failure':5,'open':55,'click':25,'conversion':10,'unsubscribe':1,'minimum_demo_funnel':1}

def _hash(value): return hashlib.sha256(value.encode()).hexdigest()

def representation(row):
    return {'id':row.id,'dataset_id':row.dataset_id,'campaign_id':row.campaign_id,'approval_id':row.approval_id,
        'validation_run_id':row.validation_run_id,'job_id':row.job_id,'status':row.status,'initial_count':row.initial_count,
        'reserved_count':row.reserved_count,'excluded_count':row.excluded_count,'sent_count':row.sent_count,
        'failed_count':row.failed_count,'response_rates':row.response_rates,'started_at':row.started_at,
        'finished_at':row.finished_at,'created_at':row.created_at}

def get_run(session,dataset_id,campaign_id,run_id):
    require_dataset(session,dataset_id)
    row=session.scalar(select(CampaignRun).where(CampaignRun.dataset_id==dataset_id,CampaignRun.campaign_id==campaign_id,CampaignRun.id==run_id))
    if row is None: raise AppError('NOT_FOUND','캠페인 실행을 찾을 수 없습니다.',404)
    counts=dict(session.execute(select(CampaignDelivery.status,func.count()).where(CampaignDelivery.run_id==row.id).group_by(CampaignDelivery.status)).all())
    result=representation(row); result['delivery_counts']={key:counts.get(key,0) for key in ('RESERVED','SENT','FAILED','EXCLUDED')}
    excluded=dict(session.execute(select(CampaignDelivery.exclusion_reason,func.count()).where(
        CampaignDelivery.run_id==row.id,CampaignDelivery.status=='EXCLUDED').group_by(CampaignDelivery.exclusion_reason)).all())
    failed=dict(session.execute(select(CampaignDelivery.exclusion_reason,func.count()).where(
        CampaignDelivery.run_id==row.id,CampaignDelivery.status=='FAILED').group_by(CampaignDelivery.exclusion_reason)).all())
    failure_summary={}
    for source in (excluded,failed):
        for key,value in source.items(): failure_summary[key or 'SYSTEM_ERROR']=failure_summary.get(key or 'SYSTEM_ERROR',0)+value
    result['failure_summary']=failure_summary
    variant_rows=session.execute(select(CampaignVariant.variant_name,CampaignDelivery.status,func.count()).join(
        CampaignDelivery,CampaignDelivery.variant_id==CampaignVariant.id).where(CampaignDelivery.run_id==row.id).group_by(
        CampaignVariant.variant_name,CampaignDelivery.status)).all()
    variants={name:{'variant_name':name,'sent':0,'failed':0,'total':0} for name in ('A','B')}
    for name,status,count in variant_rows:
        variants[name]['total']+=count
        if status=='SENT': variants[name]['sent']+=count
        elif status=='FAILED': variants[name]['failed']+=count
    result['variant_summary']=list(variants.values())
    event_rows=session.execute(select(CampaignEvent.event_type,func.count(func.distinct(CampaignEvent.customer_id))).where(
        CampaignEvent.run_id==row.id).group_by(CampaignEvent.event_type)).all()
    event_counts=dict(event_rows)
    result['event_summary']={key:event_counts.get(key,0) for key in ('DELIVERED','OPEN','CLICK','CONVERSION','UNSUBSCRIBE')}
    return result

def latest_run(session,dataset_id,campaign_id):
    require_dataset(session,dataset_id)
    row=session.scalar(select(CampaignRun).where(CampaignRun.dataset_id==dataset_id,CampaignRun.campaign_id==campaign_id).order_by(CampaignRun.created_at.desc()).limit(1))
    return None if row is None else get_run(session,dataset_id,campaign_id,row.id)

def simulate(session,campaign_id,payload,idempotency_key,request_id,*,seed_at=None,seed_value=None):
    # Offline demo seeding only: these keywords are deliberately absent from the HTTP schema.
    if (seed_at is None) != (seed_value is None):
        raise ValueError('seed_at and seed_value must be supplied together')
    if seed_at is not None and (seed_at.tzinfo is None or seed_at > datetime.now(timezone.utc)-timedelta(seconds=4)):
        raise ValueError('Demo simulation time must be timezone-aware and in the past')
    if not idempotency_key or len(idempotency_key)>200: raise AppError('IDEMPOTENCY_KEY_REQUIRED','Idempotency-Key를 입력해주세요.',422)
    canonical={'dataset_id':str(payload.dataset_id),'campaign_id':str(campaign_id),'campaign_version':payload.campaign_version}
    if seed_at is not None:
        canonical.update(seed_at=seed_at.isoformat(),seed_value=str(seed_value))
    digest=_hash(json.dumps(canonical,sort_keys=True,separators=(',',':')))
    with session.begin():
        dataset=require_dataset(session,payload.dataset_id,lock=True)
        if seed_at is not None and dataset.source!='DEMO':
            raise ValueError('Historical simulations are limited to DEMO datasets')
        campaign=campaign_repo.get(session,payload.dataset_id,campaign_id,True)
        if campaign is None: raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
        existing=session.scalar(select(CampaignRun).where(CampaignRun.campaign_id==campaign_id,CampaignRun.idempotency_key==idempotency_key).with_for_update())
        if existing:
            if existing.payload_hash!=digest: raise AppError('IDEMPOTENCY_CONFLICT','같은 키에 다른 실행 요청을 사용할 수 없습니다.')
            return representation(existing)
        if campaign.status!='APPROVED' or campaign.version!=payload.campaign_version:
            raise AppError('CAMPAIGN_NOT_APPROVED','승인된 최신 캠페인만 실행할 수 있습니다.')
        approval=policy_repo.latest_approval(session,payload.dataset_id,campaign_id)
        if approval is None or approval.status!='APPROVED': raise AppError('APPROVAL_REQUIRED','유효한 승인이 필요합니다.')
        validation=policy_repo.get_validation(session,payload.dataset_id,approval.validation_run_id,True)
        policy=policy_repr(policy_repo.setting(session,payload.dataset_id),payload.dataset_id)
        now=seed_at or datetime.now(timezone.utc)
        # The 30-minute validation window protects the transition into REVIEW/APPROVED.
        # Once a visitor has approved that exact snapshot, execution may happen later as
        # long as its campaign content, policy and source data still match. Recipient
        # safety is checked again below immediately before reservations are created.
        if validation is None or not validation.passed or validation.policy_version!=policy['version'] or validation.data_version!=data_version(session,payload.dataset_id) or validation.content_hash!=campaign_hash(session,campaign):
            raise AppError('APPROVAL_STALE','캠페인·정책·데이터가 승인 이후 변경되었습니다. 다시 검수하고 승인해주세요.')
        candidate_ids=list(session.scalars(select(ValidationRecipient.customer_id).where(
            ValidationRecipient.validation_run_id==validation.id,ValidationRecipient.eligible.is_(True)).order_by(ValidationRecipient.customer_id)))
        customers=session.scalars(select(Customer).where(Customer.dataset_id==payload.dataset_id,Customer.id.in_(candidate_ids)).order_by(Customer.id).with_for_update()).all() if candidate_ids else []
        channels=policy_repo.channels(session,payload.dataset_id,candidate_ids,campaign.channel)
        zone=ZoneInfo('Asia/Seoul'); local=now.astimezone(zone)
        day_start=local.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
        counts=policy_repo.delivery_counts(session,payload.dataset_id,candidate_ids,campaign.channel,campaign.id,day_start,now-timedelta(days=7),now) if candidate_ids else {}
        run_id=uuid4(); deliveries=[]; reserved=0
        for customer in customers:
            channel=channels.get(customer.id); duplicate,daily,weekly=counts.get(customer.id,(0,0,0))
            reasons=ordered_reasons(withdrawn=customer.status=='WITHDRAWN',consent=bool(channel and channel.consent),
                contact=channel.contact if channel else None,valid=bool(channel and channel.is_valid),hard_bounce=bool(channel and channel.hard_bounce),
                excluded=False,duplicate=duplicate>0,daily=daily,weekly=weekly,daily_limit=policy['daily_limit'],weekly_limit=policy['weekly_limit'])
            status='EXCLUDED' if reasons else 'RESERVED'; reserved+=status=='RESERVED'
            deliveries.append(CampaignDelivery(dataset_id=payload.dataset_id,campaign_id=campaign.id,run_id=run_id,
                customer_id=customer.id,channel=campaign.channel,status=status,exclusion_reason=reasons[0] if reasons else None))
        seed=_hash(str(seed_value)) if seed_value is not None else _hash(f'{campaign.id}:{validation.id}')
        job_payload={'run_id':str(run_id)}
        if seed_at is not None:
            job_payload['seed_at']=seed_at.isoformat()
        job=enqueue(session,dataset_id=payload.dataset_id,kind='campaign.simulate',key=f'run:{run_id}',payload=job_payload)
        run=CampaignRun(id=run_id,dataset_id=payload.dataset_id,campaign_id=campaign.id,approval_id=approval.id,
            validation_run_id=validation.id,job_id=job.id,idempotency_key=idempotency_key,payload_hash=digest,status='PENDING',
            seed=seed,response_rates=RATES,initial_count=len(candidate_ids),reserved_count=reserved,excluded_count=len(candidate_ids)-reserved)
        session.add(run); session.flush(); session.add_all(deliveries)
        previous=campaign.version; campaign.status='RUNNING'; campaign.version+=1
        record_change(session,dataset_id=payload.dataset_id,resource_id=campaign.id,actor_type='VISITOR',action='CAMPAIGN_SIMULATION_REQUESTED',request_id=request_id,previous_version=previous,new_version=campaign.version)
        session.flush(); return representation(run)

def _score(seed,customer_id,label): return int(_hash(f'{seed}:{customer_id}:{label}')[:8],16)%100

def simulation_job(session,job):
    run_id=UUID(job.payload['run_id'])
    run=session.scalar(select(CampaignRun).where(CampaignRun.dataset_id==job.dataset_id,CampaignRun.id==run_id).with_for_update())
    if run is None or run.job_id!=job.id: raise ValueError('Invalid campaign run job')
    if run.status=='COMPLETED': return json.loads(json.dumps(representation(run),default=str))
    campaign=campaign_repo.get(session,job.dataset_id,run.campaign_id,True)
    if campaign is None or campaign.status!='RUNNING': raise ValueError('Campaign is not running')
    now=datetime.now(timezone.utc); event_base=now-timedelta(seconds=4)
    if job.payload.get('seed_at'):
        dataset=require_dataset(session,job.dataset_id)
        event_base=datetime.fromisoformat(job.payload['seed_at'])
        if dataset.source!='DEMO' or event_base.tzinfo is None or event_base>now-timedelta(seconds=4):
            raise ValueError('Invalid historical demo execution')
        now=event_base+timedelta(seconds=4)
    run.status='RUNNING'; run.started_at=run.started_at or event_base
    variants,_=campaign_repo.children(session,campaign)
    reserved=session.scalars(select(CampaignDelivery).where(CampaignDelivery.run_id==run.id,CampaignDelivery.status=='RESERVED').order_by(CampaignDelivery.customer_id).with_for_update()).all()
    identities=dict(session.execute(select(Customer.id,Customer.external_id).where(
        Customer.dataset_id==job.dataset_id)).all()) if job.payload.get('seed_at') else {}
    identity=lambda row:identities.get(row.customer_id,row.customer_id)
    ordered=sorted(reserved,key=lambda row:(_hash(f'{run.seed}:{identity(row)}'),str(identity(row))))
    cutoff=len(ordered)*variants[0].allocation_bp//10000
    sent=failed=0
    for index,delivery in enumerate(ordered):
        customer_key=identity(delivery)
        variant=variants[0] if index<cutoff else variants[1]; delivery.variant_id=variant.id
        if _score(run.seed,customer_key,'failure')<run.response_rates['failure']:
            delivery.status='FAILED'; delivery.exclusion_reason='SYSTEM_ERROR'; failed+=1; continue
        delivery.status='SENT'; delivery.sent_at=event_base if job.payload.get('seed_at') else now; sent+=1; first_success=sent==1
        events=[('DELIVERED',0)]
        if campaign.channel=='EMAIL' and (first_success or _score(run.seed,customer_key,'open')<run.response_rates['open']): events.append(('OPEN',1))
        clicked=first_success or _score(run.seed,customer_key,'click')<run.response_rates['click']
        if clicked: events.append(('CLICK',2))
        converted=clicked and (first_success or _score(run.seed,customer_key,'conversion')<run.response_rates['conversion'])
        order=None
        if converted:
            amount=Decimal(50000+(_score(run.seed,customer_key,'amount')*1000))
            order=Order(dataset_id=job.dataset_id,customer_id=delivery.customer_id,external_id=f'sim:{run.id}:{delivery.customer_id}',
                purchased_at=event_base+timedelta(seconds=3),status='COMPLETED',amount=amount,source='SIMULATED')
            session.add(order); session.flush(); events.append(('CONVERSION',3))
        if _score(run.seed,customer_key,'unsubscribe')<run.response_rates['unsubscribe']: events.append(('UNSUBSCRIBE',4))
        for event_type,minutes in events:
            session.add(CampaignEvent(dataset_id=job.dataset_id,campaign_id=campaign.id,run_id=run.id,delivery_id=delivery.id,
                customer_id=delivery.customer_id,variant_id=variant.id,order_id=order.id if event_type=='CONVERSION' else None,
                external_id=f'sim:{run.id}:{delivery.customer_id}:{event_type}',event_type=event_type,event_at=event_base+timedelta(seconds=minutes),source='SIMULATED'))
    run.sent_count=sent; run.failed_count=failed; run.status='COMPLETED'; run.finished_at=now
    previous=campaign.version; campaign.status='COMPLETED'; campaign.version+=1
    record_change(session,dataset_id=job.dataset_id,resource_id=campaign.id,actor_type='SYSTEM',action='CAMPAIGN_SIMULATION_COMPLETED',request_id=None,previous_version=previous,new_version=campaign.version)
    session.flush(); return json.loads(json.dumps(representation(run),default=str))
