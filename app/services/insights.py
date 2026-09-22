"""Read-only entry cards calculated by existing services, without an LLM."""
from sqlalchemy import select
from app.models.campaigns import Campaign, CampaignRun, CampaignDelivery
from app.schemas.segments import PreviewRequest
from app.services import analytics, segments
from app.services.performance import campaign_performance

CANDIDATE_PROMPT = '60일 미구매, 누적 30만원 이상 고객을 저장할 초안으로 만들어줘'
CANDIDATE = {'operator':'AND','conditions':[
    {'field':'days_since_last_purchase','comparison':'GTE','value':60},
    {'field':'total_purchase_amount','comparison':'GTE','value':'300000'}]}


def generate_insights(session, query):
    metrics = analytics.overview(session, query)
    cards = []
    active = metrics['metrics']['active_customers']['value']
    total = metrics['metrics']['total_customers']['value']
    if active is not None and total:
        cards.append({'id':'active_customers','kind':'metric','title':'활성 고객 비율',
            'primary_value':f'{active:,}명','secondary_value':f'전체의 {active / total * 100:.1f}%',
            'cta':{'label':'활성 고객 수 확인','prefill_prompt':'활성 고객 수를 알려줘'}})
    # The analytics snapshot is repeatable-read. Preview needs a dataset lock;
    # finish the read-only transaction before entering the existing preview service.
    session.rollback()
    result = segments.preview(session, PreviewRequest(dataset_id=query.dataset_id, condition=CANDIDATE,
        reference_at=query.end, data_version=metrics['data_version']))
    cards.append({'id':'candidate_segment','kind':'segment_candidate','title':'캠페인 대상 후보',
        'primary_value':f'{result["count"]:,}명','secondary_value':'60일 이상 미구매 · 누적 30만원 이상',
        'cta':{'label':'이 조건으로 세그먼트 만들기','prefill_prompt':CANDIDATE_PROMPT}})
    sent_ids = select(CampaignDelivery.campaign_id).where(CampaignDelivery.dataset_id == query.dataset_id,
        CampaignDelivery.status == 'SENT', CampaignDelivery.sent_at >= query.start, CampaignDelivery.sent_at < query.end)
    latest = session.scalar(select(Campaign).join(CampaignRun, CampaignRun.campaign_id == Campaign.id).where(
        Campaign.dataset_id == query.dataset_id, Campaign.archived_at.is_(None), Campaign.status == 'COMPLETED',
        CampaignRun.dataset_id == query.dataset_id, CampaignRun.status == 'COMPLETED', Campaign.id.in_(sent_ids)).order_by(
        CampaignRun.finished_at.desc(), Campaign.id).limit(1))
    if latest:
        report = campaign_performance(session, query.dataset_id, latest.id, query.start, query.end)
        rate = report['totals']['conversion_rate']['value']
        rate_text = '전환율 집계 없음' if rate is None else f'전환율 {rate:.2f}%'
        cards.append({'id':'recent_campaign','kind':'campaign_performance','title':'최근 완료 캠페인',
            'primary_value':latest.name,'secondary_value':f'{rate_text} · 발송 {report["totals"]["sent_customers"]:,}명',
            'cta':{'label':'성과 분석하기','action':'navigate','campaign_id':str(latest.id)}})
    return {'dataset_id':query.dataset_id,'reference_at':query.end,'cards':cards}
