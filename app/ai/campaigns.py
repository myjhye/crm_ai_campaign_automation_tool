"""Prepare proposals; business writes happen only in the confirmation transaction."""
import json
import re
import time
import unicodedata
from decimal import Decimal
from zoneinfo import ZoneInfo
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal
from uuid import UUID
from sqlalchemy import select
from app.core.errors import AppError
from app.ai.provider import safe_prompt, MockProvider, OpenAIProvider, CAMPAIGN_PROMPT_VERSION
from app.models.ai import AIActionProposal, AIExecutionLog, AICopyCache
from app.repositories.imports import data_version
from app.repositories import campaigns as repository
from app.services import campaigns, segments
from app.services.datasets import require_dataset
from app.schemas.campaign import CampaignWrite, CampaignUpdate
from app.schemas.segments import PreviewRequest
from app.domain.campaigns.copy_policy import CURRENT_VERSION, POLICIES


class Copy(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    variant_name: Literal['A','B']
    subject: str = Field(max_length=200)
    body: str = Field(min_length=1,max_length=5000)
    hypothesis: str = Field(min_length=1,max_length=1000)


class GeneratedCopy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    variants: list[Copy] = Field(min_length=2,max_length=2)
    rationale: str = Field(min_length=1,max_length=1000)


class CopyRevision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: UUID
    variants: list[Copy] = Field(min_length=2,max_length=2)


def revise(session,proposal_id,request):
    from app.ai.orchestrator import payload_hash
    with session.begin():
        require_dataset(session,request.dataset_id,lock=True)
        old=session.scalar(select(AIActionProposal).where(AIActionProposal.id==proposal_id,AIActionProposal.dataset_id==request.dataset_id).with_for_update())
        if old is None or old.action_type not in ('CAMPAIGN_CREATE','CAMPAIGN_COPY'): raise AppError('NOT_FOUND','카피 제안을 찾을 수 없습니다.',404)
        if old.confirmed_at or old.expires_at<=datetime.now(timezone.utc): raise AppError('AI_PROPOSAL_EXPIRED','이미 적용되었거나 만료된 제안입니다.')
        if old.payload_hash!=payload_hash(old.payload):raise AppError('AI_PROPOSAL_CHANGED','제안이 변경되었습니다.')
        allocation={v['variant_name']:v['allocation_bp'] for v in old.payload['variants']}
        payload={**old.payload,'variants':[{**v.model_dump(),'allocation_bp':allocation[v.variant_name]} for v in request.variants]}
        model=CampaignUpdate if old.action_type=='CAMPAIGN_COPY' else CampaignWrite
        parsed=model.model_validate(payload).model_dump(mode='json')
        # This is a visitor edit; normal campaign input policy applies, not model number filtering.
        proposal=AIActionProposal(dataset_id=old.dataset_id,action_type=old.action_type,campaign_id=old.campaign_id,
            payload=parsed,payload_hash=payload_hash(parsed),data_version=old.data_version,policy_version=old.policy_version,
            expires_at=old.expires_at)
        session.add(proposal);session.flush()
        # Superseded cards cannot be used to apply an older version of this proposal.
        old.expires_at=datetime.now(timezone.utc)
        return {'proposal_id':proposal.id,'expires_at':proposal.expires_at}


def write_payload(row):
    return {key:row[key] for key in CampaignWrite.model_fields if key in row}


def number_tokens(text):
    return {(Decimal(number.replace(',', '')), unit) for number,unit in
        re.findall(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(%|원|일|시간|개|명)?',unicodedata.normalize('NFKC',text))}


def normalized_benefit(text):
    text=unicodedata.normalize('NFKC',text)
    text=re.sub(r'(?<=\d),(?=\d{3}(?:\D|$))','',text)
    return re.sub(r'\s+','',text)


def expiry_labels(value):
    """Render the actual expiry in the UI's timezone, never whitelist date parts."""
    if not value:
        return []
    at=datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Seoul'))
    return [f'{at.year}년 {at.month}월 {at.day}일 {at.hour:02}:{at.minute:02}',
        f'{at.year}년 {at.month}월 {at.day}일', f'{at.month}월 {at.day}일',
        at.strftime('%Y-%m-%d %H:%M'),at.strftime('%Y-%m-%d')]


def unsupported_numbers(text,base):
    # Match a complete, correct calendar date before checking other numeric claims.
    # An ISO date's individual numbers must not authorize invented durations/discounts.
    for label in expiry_labels(base.get('coupon_expires_at')):
        pattern=r'(?<!\d)'+r'\s*'.join(re.escape(part) for part in label.split())+r'(?!\d)'
        text=re.sub(pattern,'',text)
    return number_tokens(text)-number_tokens(base['benefit'])


def validate_generated(args, base):
    generated=GeneratedCopy.model_validate(args)
    if {v.variant_name for v in generated.variants}!={'A','B'}:
        raise ValueError('A/B 두 안이 필요합니다.')
    for variant in generated.variants:
        text=variant.subject+'\n'+variant.body
        safe_prompt(text)
        if normalized_benefit(base['benefit']) not in normalized_benefit(variant.body):
            raise ValueError('본문에 입력한 혜택 문구가 빠졌거나 변경되었습니다.')
        if unsupported_numbers(text,base):
            raise ValueError('입력한 혜택·만료일에 없는 숫자나 단위가 포함되었습니다.')
    allocation={v['variant_name']:v['allocation_bp'] for v in base['variants']}
    payload={**base,'variants':[{**v.model_dump(),'allocation_bp':allocation[v.variant_name]} for v in generated.variants]}
    try:
        payload=CampaignWrite.model_validate(payload).model_dump(mode='json')
    except ValidationError:
        raise ValueError('채널별 제목·본문 길이 또는 카피 정책을 충족하지 못했습니다.') from None
    return generated,payload


def propose(database, settings, query, request_id, provider=None):
    from app.ai.orchestrator import payload_hash
    if bool(query.campaign_brief) == bool(query.campaign_id):
        raise AppError('AI_CAMPAIGN_INPUT','새 캠페인 조건 또는 기존 캠페인 중 하나를 선택해주세요.',422)
    started = time.monotonic(); status='FAILED'; tokens=0
    operation = 'generate_copy' if query.campaign_id else 'create_campaign_draft'
    with database.sessions() as session: require_dataset(session,query.dataset_id)
    try:
        safe_prompt(query.prompt)
        with database.sessions() as session:
            require_dataset(session,query.dataset_id,lock=True)
            version = data_version(session,query.dataset_id)
            if query.campaign_id:
                row = campaigns.detail(session,query.dataset_id,query.campaign_id)
                if row['status'] != 'DRAFT' or row['version'] != query.campaign_version:
                    raise AppError('VERSION_CONFLICT','캠페인이 변경되었습니다. 최신 캠페인을 다시 선택해주세요.')
                base = write_payload(row)
                # Never return IDs from existing variant rows in a write payload.
                base['variants'] = [{k:v[k] for k in ('variant_name','subject','body','hypothesis','allocation_bp')} for v in row['variants']]
                campaign_version = row['version']
            else:
                base = {**query.campaign_brief.model_dump(mode='json'),'dataset_id':str(query.dataset_id),
                    'variants':[{'variant_name':n,'subject':'' if query.campaign_brief.channel=='SMS' else '초안',
                        'body':'초안','hypothesis':'초안','allocation_bp':5000} for n in ['A','B']]}
                campaign_version = None
            base = CampaignWrite.model_validate(base).model_dump(mode='json')
            revision = repository.revisions(session,query.dataset_id,[base['segment_revision_id']])
            if not revision: raise AppError('NOT_FOUND','대상 세그먼트를 찾을 수 없습니다.',404)
            revision = revision[0]
            aggregate = segments.preview(session,PreviewRequest(dataset_id=query.dataset_id,condition=revision.condition_json,
                reference_at=revision.reference_at,data_version=version))
            profile = segments.ai_profile(aggregate)
            # Transaction ends before the external model is contacted.
        brief = {k:base[k] for k in ('name','objective','channel','benefit','brand_tone','coupon_expires_at')}
        safe_prompt(json.dumps(brief,ensure_ascii=False))
        safe_prompt(json.dumps(profile,ensure_ascii=False))
        policy = POLICIES[CURRENT_VERSION][base['channel']]
        if len(base['benefit']) > policy['body_max']:
            raise AppError('AI_BENEFIT_TOO_LONG','혜택 설명을 채널 본문 제한보다 짧게 입력해주세요.',422)
        provider = provider or (MockProvider() if settings.ai_mode=='mock' else OpenAIProvider(settings))
        context={'operation':operation,'campaign':brief,'profile':profile,'copy_policy':policy,
            'reference_at':revision.reference_at.isoformat(),
            'coupon_expiry_display':next(iter(expiry_labels(base['coupon_expires_at'])),None)}
        cache_key=payload_hash({'dataset_id':str(query.dataset_id),'data_version':version,
            'segment_revision_id':str(revision.id),'context':context,'prompt':query.prompt.strip(),
            'settings':{k:v for k,v in base.items() if k!='variants'},
            'provider':settings.ai_mode,'model':settings.ai_model,'implementation':type(provider).__qualname__,
            'prompt_version':CAMPAIGN_PROMPT_VERSION,'policy_version':CURRENT_VERSION,
            'max_output_tokens':settings.ai_max_output_tokens})
        with database.sessions() as session:
            cached=session.get(AICopyCache,cache_key)
            cached_args=cached.generated if cached else None
        cache_hit=cached_args is not None
        if cache_hit:
            generated,base=validate_generated(cached_args,base)
        else:
            for attempt in range(2):
                name,args,used_tokens=provider.plan(query.prompt,context)
                tokens+=used_tokens
                try:
                    if name!=operation: raise ValueError('요청한 카피 도구 결과가 아닙니다.')
                    generated,payload=validate_generated(args,base)
                    base=payload
                    break
                except (ValueError,TypeError) as error:
                    reason='A/B 응답 형식이 올바르지 않습니다.' if isinstance(error,(ValidationError,TypeError)) else str(error)
                    if attempt:
                        raise AppError('AI_INVALID_COPY',reason+' 자동 재생성도 실패했습니다. 입력 내용은 유지됩니다.',502) from None
                    context['validation_feedback']=reason+' 혜택 문구를 그대로 포함하고 허용되지 않은 숫자는 사용하지 마세요.'
        if campaign_version is not None: base['version'] = campaign_version
        with database.sessions.begin() as session:
            require_dataset(session,query.dataset_id,lock=True)
            if data_version(session,query.dataset_id) != version: raise AppError('DATA_VERSION_CONFLICT','데이터가 변경되었습니다. 다시 생성해주세요.')
            if query.campaign_id:
                latest = repository.get(session,query.dataset_id,query.campaign_id,lock=True)
                if latest.version != campaign_version or latest.status != 'DRAFT': raise AppError('VERSION_CONFLICT','캠페인이 변경되었습니다. 다시 생성해주세요.')
            # Dataset lock serializes publication: simultaneous misses return the first valid copy.
            winner=session.get(AICopyCache,cache_key)
            if winner:
                generated,validated=validate_generated(winner.generated,{k:v for k,v in base.items() if k!='version'})
                base.update(validated)
                cache_hit=True
            else:
                session.add(AICopyCache(cache_key=cache_key,dataset_id=query.dataset_id,
                    generated=generated.model_dump(mode='json'),created_at=datetime.now(timezone.utc)))
            proposal = AIActionProposal(dataset_id=query.dataset_id,action_type='CAMPAIGN_COPY' if query.campaign_id else 'CAMPAIGN_CREATE',
                campaign_id=query.campaign_id,payload=base,payload_hash=payload_hash(base),data_version=version,
                policy_version=CURRENT_VERSION,expires_at=datetime.now(timezone.utc)+timedelta(minutes=30))
            session.add(proposal); session.flush()
            result = {**base,'proposal_id':proposal.id,'expires_at':proposal.expires_at,'rationale':generated.rationale,
                'operation':operation,'source_version':campaign_version,'profile':profile}
        status='SUCCESS'
        return {'message':'A/B 카피와 혜택을 확인한 뒤 적용해주세요.','result_type':'campaign_draft','data':result,
            'mode':settings.ai_mode,'cache_hit':cache_hit,'dataset_id':query.dataset_id,'reference_at':revision.reference_at,'data_version':version,'request_id':request_id}
    except (ValueError,TypeError,ValidationError):
        raise AppError('AI_INVALID_COPY','생성된 카피가 혜택 또는 채널 기준에 맞지 않습니다. 조건을 구체화해 다시 요청해주세요.',502) from None
    finally:
        with database.sessions.begin() as session:
            session.add(AIExecutionLog(dataset_id=query.dataset_id,request_id=request_id,provider=settings.ai_mode,conversation_id=query.conversation_id,
                model=settings.ai_model if settings.ai_mode=='live' else 'fixture',prompt_version=CAMPAIGN_PROMPT_VERSION,status=status,
                tool_name=operation,elapsed_ms=int((time.monotonic()-started)*1000),total_tokens=tokens))


def apply(session,proposal,request_id):
    if proposal.data_version != data_version(session,proposal.dataset_id) or proposal.policy_version != CURRENT_VERSION:
        raise AppError('AI_PROPOSAL_STALE','데이터 또는 정책이 변경되었습니다. 다시 생성해주세요.')
    if proposal.action_type == 'CAMPAIGN_COPY':
        result = campaigns.save(session,CampaignUpdate.model_validate(proposal.payload),request_id,proposal.campaign_id,managed_transaction=True)
    else:
        result = campaigns.save(session,CampaignWrite.model_validate(proposal.payload),request_id,managed_transaction=True)
    proposal.campaign_id = result['id']
    proposal.confirmed_at = datetime.now(timezone.utc)
    return result
