"""Interpret a short request, then reuse the existing validated copy generator."""
import json
import time
from sqlalchemy import select
from app.ai.schemas import CampaignBrief
from app.ai.provider import MockProvider,OpenAIProvider,safe_prompt
from app.ai.campaigns import propose,normalized_benefit
from app.models.segments import Segment,SegmentRevision
from app.services.datasets import require_dataset
from app.core.errors import AppError
from pydantic import ValidationError
from app.models.ai import AIExecutionLog


def plan(database,settings,query,request_id,provider=None):
    safe_prompt(query.prompt)
    if query.campaign_setup:
        setup=query.campaign_setup
        if setup.a_focus==setup.b_focus:
            raise AppError('INVALID_EXPERIMENT','A안과 B안의 강조점을 다르게 선택해주세요.',422)
        with database.sessions() as session:
            require_dataset(session,query.dataset_id)
            segment_name=session.scalar(select(Segment.name).join(SegmentRevision,
                (Segment.id==SegmentRevision.segment_id)&(Segment.version==SegmentRevision.version)).where(
                Segment.dataset_id==query.dataset_id,Segment.archived_at.is_(None),SegmentRevision.id==setup.segment_revision_id))
        if segment_name is None:raise AppError('AI_INVALID_TARGET','대상 세그먼트를 다시 선택해주세요.',409)
        brief=CampaignBrief(segment_revision_id=setup.segment_revision_id,name=f'{segment_name} · {setup.objective}'[:200],
            objective=setup.objective,channel=setup.channel,benefit=setup.benefit,brand_tone=setup.brand_tone,
            primary_kpi=setup.primary_kpi,target_value=setup.target_value)
        prompt=f'확정된 설정으로 추가 질문 없이 카피를 생성하세요. 공통 브랜드 톤: {setup.brand_tone}. A안: {setup.a_focus}. B안: {setup.b_focus}. 추가 요청: {query.prompt}'
        result=propose(database,settings,query.model_copy(update={'campaign_brief':brief,'campaign_setup':None,'campaign_id':None,'campaign_version':None,'prompt':prompt}),request_id,provider)
        result['segment_name']=segment_name
        result['notice']='선택한 설정과 A/B 50:50 비율을 적용합니다. 제외 조건·예정일·만료일은 기존 폼 값을 유지합니다.'
        return result
    with database.sessions() as session:
        require_dataset(session,query.dataset_id)
        rows=session.execute(select(SegmentRevision.id,Segment.name).join(Segment,
            (Segment.id==SegmentRevision.segment_id)&(Segment.version==SegmentRevision.version)).where(
            Segment.dataset_id==query.dataset_id,Segment.archived_at.is_(None)).order_by(Segment.id).limit(101)).all()
    if not rows:
        return {'result_type':'clarification','message':'먼저 대상 세그먼트를 저장해주세요.'}
    if len(rows)>100:
        return {'result_type':'clarification','message':'세그먼트가 많습니다. 메인 폼에서 대상을 선택하고 카피만 수정을 이용해주세요.'}
    options=[{'id':str(r.id),'name':r.name} for r in rows]
    # UUIDs are server-issued identifiers, not user text. Scanning their random
    # digit runs can produce false positives for the resident-number pattern.
    safe_prompt(json.dumps([option['name'] for option in options],ensure_ascii=False))
    provider=provider or (MockProvider() if settings.ai_mode=='mock' else OpenAIProvider(settings))
    started=time.monotonic();status='FAILED';tokens=0
    try:
        name,args,tokens=provider.plan(query.prompt,{'brief_schema':CampaignBrief.model_json_schema(),'segments':options})
        status='SUCCESS'
    finally:
        with database.sessions.begin() as session:
            session.add(AIExecutionLog(dataset_id=query.dataset_id,request_id=request_id,provider=settings.ai_mode,
                model=settings.ai_model if settings.ai_mode=='live' else 'fixture',prompt_version='ai-b-plan-1',
                status=status,tool_name='plan_campaign',elapsed_ms=int((time.monotonic()-started)*1000),total_tokens=tokens))
    if name!='plan_campaign' or not isinstance(args,dict):raise AppError('AI_INVALID_BRIEF','캠페인 조건을 해석하지 못했습니다.',502)
    if args.get('question'):
        return {'result_type':'clarification','message':str(args['question'])[:1000]}
    try:brief=CampaignBrief.model_validate_json(args['brief_json'])
    except (KeyError,TypeError,ValidationError):raise AppError('AI_INVALID_BRIEF','캠페인 조건 형식이 올바르지 않습니다.',502) from None
    if str(brief.segment_revision_id) not in {o['id'] for o in options}:
        raise AppError('AI_INVALID_TARGET','저장된 세그먼트 중 대상을 선택하지 못했습니다.',502)
    if normalized_benefit(brief.benefit) not in normalized_benefit(query.prompt):
        return {'result_type':'clarification','message':'제공할 혜택을 정확히 입력해주세요. 예: 15% 할인 쿠폰'}
    brief.coupon_expires_at=None
    result=propose(database,settings,query.model_copy(update={'campaign_brief':brief,'campaign_id':None,'campaign_version':None}),request_id,provider)
    result['segment_name']=next(o['name'] for o in options if o['id']==str(brief.segment_revision_id))
    result['notice']='전체 초안은 추천입니다. KPI 목표와 50:50 비율을 확인해주세요. 제외 조건·예정일·만료일은 적용 시 기존 입력을 유지합니다.'
    return result
