"""Evidence-bound analysis. The model selects claims, never invents metric values."""
from datetime import datetime, timezone, timedelta
from uuid import UUID
import time
import logging

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.ai.provider import MockProvider, OpenAIProvider, safe_prompt
from app.ai.tools import tool
from app.ai.orchestrator import payload_hash
from app.core.errors import AppError
from app.models.ai import AIActionProposal, AIExecutionLog
from app.models.campaigns import PolicySetting
from app.repositories import campaigns as repository
from app.repositories.imports import data_version
from app.schemas.analytics import AnalyticsQuery
from app.schemas.campaign import CampaignWrite
from app.services import campaigns
from app.services.datasets import require_dataset
from app.services.performance import campaign_performance

PROMPT_VERSION = 'ai-d-3'
MAX_FACTS = 12
MAX_HYPOTHESES = 2
MAX_ACTIONS = 2
logger = logging.getLogger(__name__)
HYPOTHESES = {
    'COPY_RESPONSE': '문안의 표현 차이가 반응 차이에 기여했을 가능성이 있습니다. 원인으로 확정할 수 없으며 동일 조건의 추가 실험이 필요합니다.',
    'RANDOM_VARIATION': '관측된 차이는 표본 변동의 영향일 수 있습니다. 수치상 우세만으로 승자를 확정할 수 없습니다.',
}
ACTIONS = {
    'RETEST': '같은 A/B 조건으로 추가 실험을 준비하고 표본을 늘려 재검증하세요.',
    'REVIEW_COPY': '수신거부와 문안의 부담감을 검토한 뒤 다음 실험의 변경점을 정하세요.',
}
REASONS = {'OBSERVATION_OPEN':'관찰 기간 진행 중', 'INSUFFICIENT_SAMPLE':'표본 부족',
    'GUARDRAIL_WORSE':'수신거부율 악화', 'REVENUE_SIGNIFICANCE_NOT_AVAILABLE':'매출 주지표의 통계 판정 미지원',
    'NO_SIGNIFICANT_DIFFERENCE':'통계적으로 유의한 차이를 확인하지 못했습니다'}


class PerformanceRequest(AnalyticsQuery):
    campaign_id: UUID
    prompt: str = Field(default='성과의 근거와 한계를 설명하고 다음 실험을 제안해주세요.', min_length=1, max_length=2000)


class Fact(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    metric_id: str


class AnalysisSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    facts: list[Fact] = Field(min_length=1, max_length=MAX_FACTS)
    hypotheses: list[str] = Field(max_length=MAX_HYPOTHESES)
    recommended_actions: list[str] = Field(min_length=1, max_length=MAX_ACTIONS)


def evidence(report):
    refs = {}
    for scope, row in [('total', report['totals']), *[(v['name'], v) for v in report['variants']]]:
        for key, label, unit in [('delivered_customers','전달 고객','명'), ('conversion_customers','전환 고객','명'),
                                  ('click_rate','클릭률','%'), ('conversion_rate','전환율','%'),
                                  ('unsubscribe_rate','수신거부율','%'), ('revenue','기여 매출','원')]:
            value = row[key]
            if isinstance(value, dict): value = value['value']
            if value is not None:
                refs[f'{scope}.{key}'] = {'label': f'{"전체" if scope == "total" else scope + "안"} {label}', 'value': str(value), 'unit': unit}
    if report['experiment']['primary_kpi'] != 'revenue':
        for key,label,unit in [('p_value','p-value',''),('absolute_difference_pp','B−A 주요 지표 차이','%p')]:
            value=report['experiment'][key]
            if value is not None: refs[f'experiment.{key}']={'label':label,'value':str(value),'unit':unit}
    return refs


def analysis_tool(refs):
    return tool('analyze_campaign', '서버 성과 근거를 선택하고 검증 전 가설과 다음 실험을 제안합니다.', {
        'facts': {'type':'array','minItems':1,'maxItems':MAX_FACTS,'items':{'type':'object','properties':{
            'metric_id':{'type':'string','enum':list(refs)}},
            'required':['metric_id'],'additionalProperties':False}},
        'hypotheses': {'type':'array','maxItems':MAX_HYPOTHESES,'items':{'type':'string','enum':list(HYPOTHESES)}},
        'recommended_actions': {'type':'array','minItems':1,'maxItems':MAX_ACTIONS,'items':{'type':'string','enum':list(ACTIONS)}},
    })


def validate_selection(args, refs, report):
    parsed = AnalysisSelection.model_validate(args)
    if len({f.metric_id for f in parsed.facts}) != len(parsed.facts): raise ValueError('Duplicate facts')
    for fact in parsed.facts:
        if fact.metric_id not in refs:
            raise ValueError('Unsupported metric')
    if not set(parsed.hypotheses) <= HYPOTHESES.keys() or not set(parsed.recommended_actions) <= ACTIONS.keys():
        raise ValueError('Unsupported interpretation')
    if report['experiment']['winner'] and 'RANDOM_VARIATION' in parsed.hypotheses:
        raise ValueError('Contradictory verdict')
    return parsed


def snapshot(report):
    # calculated_at is volatile; evidence, cohort, observation cutoff and verdict are not.
    return payload_hash(jsonable_encoder({k:report[k] for k in ('totals','variants','experiment','cohort','observation','contains_simulated_data')}))


def policy_version(session, dataset_id):
    return session.scalar(select(PolicySetting.version).where(PolicySetting.dataset_id == dataset_id)) or 1


def analyze(database, settings, query, request_id, provider=None):
    started=time.monotonic(); status='FAILED'; tokens=0; stage='prepare'
    with database.sessions() as session: require_dataset(session,query.dataset_id)
    try:
        prompt=safe_prompt(query.prompt)
        cutoff=datetime.now(timezone.utc)
        with database.sessions() as session:
            source=campaigns.detail(session,query.dataset_id,query.campaign_id)
            if source['status']!='COMPLETED': raise AppError('AI_PERFORMANCE_NOT_READY','발송이 완료된 캠페인을 선택해주세요.',422)
            version=data_version(session,query.dataset_id)
            policy=policy_version(session,query.dataset_id)
            report=campaign_performance(session,query.dataset_id,query.campaign_id,query.start,query.end,cutoff)
        if not report['totals']['sent_customers']:
            raise AppError('AI_PERFORMANCE_EMPTY','선택 기간에 발송된 고객이 없습니다. 기간을 변경해주세요.',422)
        refs=evidence(report)
        # No names, copies, customer rows or contact details leave the server.
        context={'performance':{'metric_refs':refs,'experiment':report['experiment'],
            'contains_simulated_data':report['contains_simulated_data'], 'hypotheses':HYPOTHESES,'actions':ACTIONS},
            'analysis_tool':analysis_tool(refs)}
        provider=provider or (MockProvider() if settings.ai_mode=='mock' else OpenAIProvider(settings))
        stage='provider'
        name,args,tokens=provider.plan(prompt,context)
        stage='selection'
        if name!='analyze_campaign': raise ValueError('Wrong tool')
        selection=validate_selection(args,refs,report)
        limits=['이 분석은 두 발송안의 비교이며 무발송 대비 증분 효과나 인과관계를 증명하지 않습니다.',
            '기여 매출은 마지막 클릭 기준 귀속입니다. 기기·랜딩페이지별 원인 데이터는 제공되지 않습니다.',
            '시연은 안별 최소 표본 30명과 발송 완료 즉시 판정을 사용합니다. 실제 운영 실험에서는 표본과 관찰 기간을 사전에 설계해야 합니다.']
        if report['contains_simulated_data']: limits.insert(0,'모의 발송으로 생성된 합성 성과입니다. 실제 고객 반응이나 사업 성과가 아닙니다.')
        test=report['experiment']
        conclusion=(f"{test['winner']}안 우세 · 기존 통계 검정 결과입니다." if test['winner'] else
            '승자 확정 불가 · '+' · '.join(REASONS.get(reason,reason) for reason in test['reasons']))
        if not test['winner']: limits.append(conclusion)
        from app.ai.campaigns import write_payload
        base=write_payload(source)
        base['variants']=[{k:v[k] for k in ('variant_name','subject','body','hypothesis','allocation_bp')} for v in source['variants']]
        base.update(name=source['name'][:180]+' · 후속 실험',planned_at=None)
        stage='followup_draft'
        draft=CampaignWrite.model_validate(base).model_dump(mode='json')
        envelope={'dataset_id':str(query.dataset_id),'source_id':str(query.campaign_id),'source_version':source['version'],
            'from':query.start.isoformat(),'to':query.end.isoformat(),'observation_to':cutoff.isoformat(),
            'evidence_hash':snapshot(report),'draft':draft}
        proposal_data=None
        stage='publish'
        with database.sessions.begin() as session:
            require_dataset(session,query.dataset_id,lock=True)
            latest=repository.get(session,query.dataset_id,query.campaign_id,lock=True)
            if latest is None or latest.version!=source['version'] or latest.status!='COMPLETED' or data_version(session,query.dataset_id)!=version or policy_version(session,query.dataset_id)!=policy:
                raise AppError('AI_ANALYSIS_STALE','분석 중 데이터나 캠페인이 변경되었습니다. 다시 분석해주세요.')
            current=campaign_performance(session,query.dataset_id,query.campaign_id,query.start,query.end,cutoff)
            if snapshot(current)!=envelope['evidence_hash']: raise AppError('AI_ANALYSIS_STALE','성과가 변경되었습니다. 다시 분석해주세요.')
            if 'RETEST' in selection.recommended_actions:
                proposal=AIActionProposal(dataset_id=query.dataset_id,action_type='CAMPAIGN_FOLLOWUP',payload=envelope,
                    payload_hash=payload_hash(envelope),data_version=version,policy_version=policy,
                    expires_at=cutoff+timedelta(minutes=30))
                session.add(proposal);session.flush()
                proposal_data={'proposal_id':proposal.id,'expires_at':proposal.expires_at,'draft':draft,
                    'segment_name':report['campaign']['segment_name']}
        status='SUCCESS'
        return {'message':'성과의 근거와 해석의 한계를 확인해주세요.','result_type':'performance_analysis','mode':settings.ai_mode,'request_id':request_id,'dataset_id':query.dataset_id,
            'data_version':version,'reference_at':cutoff,
            'data':{'campaign_id':query.campaign_id,'campaign_name':source['name'],'facts':[{'metric_id':f.metric_id,**refs[f.metric_id]} for f in selection.facts],
                'hypotheses':[HYPOTHESES[h] for h in dict.fromkeys(selection.hypotheses)],'limitations':limits,
                'recommended_actions':[{'code':a,'target_id':query.campaign_id,'text':ACTIONS[a]} for a in dict.fromkeys(selection.recommended_actions)],
                'metric_refs':refs,'experiment':test,'conclusion':conclusion,'cohort':report['cohort'],'reference_at':cutoff,'proposal':proposal_data}}
    except (ValueError,TypeError) as error:
        # Never log prompts, model arguments, metric values or validation exception text.
        logger.warning('AI analysis validation failed request_id=%s stage=%s error_type=%s',request_id,stage,type(error).__name__)
        raise AppError('AI_INVALID_ANALYSIS','AI 분석을 실제 지표와 대조하지 못했습니다. 다시 요청해주세요.',502) from None
    finally:
        with database.sessions.begin() as session:
            session.add(AIExecutionLog(dataset_id=query.dataset_id,request_id=request_id,provider=settings.ai_mode,
                model=settings.ai_model if settings.ai_mode=='live' else 'fixture',prompt_version=PROMPT_VERSION,
                status=status,tool_name='analyze_campaign',elapsed_ms=int((time.monotonic()-started)*1000),total_tokens=tokens))


def apply_followup(session, proposal, request_id):
    payload=proposal.payload; did=proposal.dataset_id
    source=repository.get(session,did,UUID(payload['source_id']),lock=True)
    if source is None or source.version!=payload['source_version'] or source.status!='COMPLETED' or data_version(session,did)!=proposal.data_version or policy_version(session,did)!=proposal.policy_version:
        raise AppError('AI_PROPOSAL_STALE','원본 캠페인·데이터·정책이 변경되었습니다. 다시 분석해주세요.')
    report=campaign_performance(session,did,source.id,datetime.fromisoformat(payload['from']),datetime.fromisoformat(payload['to']),datetime.fromisoformat(payload['observation_to']))
    if snapshot(report)!=payload['evidence_hash']: raise AppError('AI_PROPOSAL_STALE','성과 근거가 변경되었습니다. 다시 분석해주세요.')
    result=campaigns.save(session,CampaignWrite.model_validate(payload['draft']),request_id,managed_transaction=True)
    proposal.campaign_id=result['id'];proposal.confirmed_at=datetime.now(timezone.utc)
    return result
