from bisect import bisect_right
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select
from app.core.errors import AppError
from app.models.campaigns import Campaign,CampaignDelivery,CampaignEvent
from app.models.customers import Order
from app.models.segments import SegmentRevision
from app.services.datasets import require_dataset
from app.repositories import campaigns as campaign_repo
from app.domain.analytics.experiment import ratio,compare

MODEL='last_click_7d_v1'
# 포트폴리오 시연용: 발송 완료 즉시 판정한다. 실제 서비스에서는 구매 주기에 맞는 관찰 기간을 사전에 고정해야 함.
EXPERIMENT_OBSERVATION_DAYS=0

def _money(value):return format(value.quantize(Decimal('0.01')),'f')

def _attributions(session,dataset_id,observation_to):
    clicks=session.execute(select(CampaignEvent.customer_id,CampaignEvent.event_at,CampaignEvent.id,CampaignEvent.campaign_id,CampaignEvent.variant_id).where(
        CampaignEvent.dataset_id==dataset_id,CampaignEvent.event_type=='CLICK',CampaignEvent.event_at<observation_to).order_by(CampaignEvent.customer_id,CampaignEvent.event_at,CampaignEvent.id)).all()
    by_customer=defaultdict(list)
    for row in clicks:by_customer[row.customer_id].append(row)
    orders=session.scalars(select(Order).where(Order.dataset_id==dataset_id,Order.status=='COMPLETED',Order.purchased_at<observation_to).order_by(Order.purchased_at,Order.id)).all()
    result=[]
    for order in orders:
        rows=by_customer.get(order.customer_id,[])
        keys=[(row.event_at,row.id.int) for row in rows]
        index=bisect_right(keys,(order.purchased_at,(1<<128)-1))-1
        if index>=0:
            click=rows[index]
            if click.event_at>=order.purchased_at-timedelta(days=7):result.append((order,click))
    return result

def campaign_performance(session,dataset_id:UUID,campaign_id:UUID,start:datetime,end:datetime,observation_to:datetime|None=None,*,include_archived=False):
    require_dataset(session,dataset_id)
    campaign=campaign_repo.get(session,dataset_id,campaign_id,include_archived=include_archived)
    if campaign is None:raise AppError('NOT_FOUND','캠페인을 찾을 수 없습니다.',404)
    observation_to=min(observation_to or datetime.now(timezone.utc),datetime.now(timezone.utc))
    variants,_=campaign_repo.children(session,campaign)
    segment_name=session.scalar(select(SegmentRevision.name).where(SegmentRevision.id==campaign.segment_revision_id,SegmentRevision.dataset_id==dataset_id))
    deliveries=session.scalars(select(CampaignDelivery).where(CampaignDelivery.dataset_id==dataset_id,CampaignDelivery.campaign_id==campaign_id,
        CampaignDelivery.status=='SENT',CampaignDelivery.sent_at>=start,CampaignDelivery.sent_at<end)).all()
    delivery_ids=[row.id for row in deliveries];customer_ids={row.customer_id for row in deliveries}
    events=session.scalars(select(CampaignEvent).where(CampaignEvent.dataset_id==dataset_id,CampaignEvent.campaign_id==campaign_id,
        CampaignEvent.delivery_id.in_(delivery_ids),CampaignEvent.event_at<observation_to)).all() if delivery_ids else []
    event_customers=defaultdict(set);variant_events=defaultdict(lambda:defaultdict(set))
    for event in events:
        event_customers[event.event_type].add(event.customer_id);variant_events[event.variant_id][event.event_type].add(event.customer_id)
    attributed=[(order,click) for order,click in _attributions(session,dataset_id,observation_to) if click.campaign_id==campaign_id and order.customer_id in customer_ids]
    converted={order.customer_id for order,_ in attributed};revenue=sum((order.amount for order,_ in attributed),Decimal('0'))
    delivered=len(event_customers['DELIVERED'])
    def metrics_for(variant_id=None):
        scoped=[row for row in deliveries if variant_id is None or row.variant_id==variant_id];den=len({row.customer_id for row in scoped})
        event_map=event_customers if variant_id is None else variant_events[variant_id]
        scoped_customers={row.customer_id for row in scoped};orders=[(order,click) for order,click in attributed if click.variant_id==variant_id] if variant_id else attributed
        conversions={order.customer_id for order,_ in orders};amount=sum((order.amount for order,_ in orders),Decimal('0'))
        opens=len(event_map['OPEN']);clicks=len(event_map['CLICK']);unsubs=len(event_map['UNSUBSCRIBE'])
        open_metric={'status':'not_applicable','numerator':None,'denominator':den,'value':None} if campaign.channel!='EMAIL' else ratio(opens,den)
        ctor={'status':'data_quality_error','numerator':clicks,'denominator':opens,'value':None} if clicks>opens else ratio(clicks,opens)
        return {'sent_customers':den,'delivered_customers':len(event_map['DELIVERED']),'open_customers':opens,'click_customers':clicks,
            'conversion_customers':len(conversions),'unsubscribe_customers':unsubs,'revenue':_money(amount),'revenue_per_delivered':None if not den else _money(amount/den),
            'open_rate':open_metric,'click_rate':ratio(clicks,den),'ctor':ctor,'conversion_rate':ratio(len(conversions),den),'unsubscribe_rate':ratio(unsubs,den)}
    variant_results=[]
    for variant in variants:variant_results.append({'id':variant.id,'name':variant.variant_name,**metrics_for(variant.id)})
    latest_sent=max((row.sent_at for row in deliveries),default=None);observation_end=latest_sent+timedelta(days=EXPERIMENT_OBSERVATION_DAYS) if latest_sent else end
    a=next((row for row in variant_results if row['name']=='A'),{'conversion_customers':0,'click_customers':0,'delivered_customers':0,'unsubscribe_rate':{'value':None}})
    b=next((row for row in variant_results if row['name']=='B'),{'conversion_customers':0,'click_customers':0,'delivered_customers':0,'unsubscribe_rate':{'value':None}})
    guardrail=(b['unsubscribe_rate']['value'] or 0)>(a['unsubscribe_rate']['value'] or 0)+1
    success_field='click_customers' if campaign.primary_kpi=='click_rate' else 'conversion_customers'
    experiment=compare(a[success_field],a['delivered_customers'],b[success_field],b['delivered_customers'],observation_to>=observation_end,guardrail)
    experiment['primary_kpi']=campaign.primary_kpi
    if campaign.primary_kpi=='revenue':
        experiment.update(status='HOLD',winner=None,reasons=['REVENUE_SIGNIFICANCE_NOT_AVAILABLE'])
    return {'campaign':{'id':campaign.id,'name':campaign.name,'channel':campaign.channel,'status':campaign.status,'primary_kpi':campaign.primary_kpi,
        'segment_revision_id':campaign.segment_revision_id,'segment_name':segment_name},
        'cohort':{'from':start,'to':end},'observation':{'to':observation_to,'ends_at':observation_end,'complete':observation_to>=observation_end,'window_days':EXPERIMENT_OBSERVATION_DAYS},
        'attribution':{'model':MODEL,'window_days':7,'calculated_at':datetime.now(timezone.utc)},'contains_simulated_data':any(event.source=='SIMULATED' for event in events),
        'totals':metrics_for(),'variants':variant_results,'experiment':experiment,
        'incremental_conversion_rate':{'status':'not_available','value':None},'incremental_revenue':{'status':'not_available','value':None}}

def campaign_rows(session,dataset_id,start,end,observation_to=None):
    campaigns=session.scalars(select(Campaign).where(Campaign.dataset_id==dataset_id,Campaign.status=='COMPLETED').order_by(Campaign.created_at.desc())).all()
    rows=[campaign_performance(session,dataset_id,row.id,start,end,observation_to,include_archived=True) for row in campaigns]
    return [row for row in rows if row['totals']['sent_customers']>0]


def compare_campaigns(session, dataset_id, args, default_from, default_to, context_hint=None):
    """Compare sent cohorts, matching Reports. Rates are already percentages."""
    from app.ai.workspace_schemas import CompareRequest
    from app.schemas.common import ReportingPeriod
    from app.models.campaigns import CampaignRun
    from app.models.segments import Segment
    from sqlalchemy import func
    parsed = CompareRequest.model_validate(args)
    period = ReportingPeriod(start=parsed.filter.start or default_from, end=parsed.filter.end or default_to)
    require_dataset(session, dataset_id)
    query = select(Campaign).where(Campaign.dataset_id == dataset_id, Campaign.status == 'COMPLETED', Campaign.archived_at.is_(None))
    if parsed.filter.channel != 'ANY':
        query = query.where(Campaign.channel == parsed.filter.channel)
    revision_id = parsed.filter.segment_revision_id
    if revision_id:
        revision = session.scalar(select(SegmentRevision).join(Segment, Segment.id == SegmentRevision.segment_id).where(
            SegmentRevision.dataset_id == dataset_id, SegmentRevision.id == UUID(revision_id), Segment.archived_at.is_(None)))
        if revision is None:
            raise AppError('INVALID_SEGMENT', '이 데이터셋의 세그먼트를 선택해주세요.', 422)
        query = query.where(Campaign.segment_revision_id == revision.id)
    if context_hint:
        if context_hint['kind'] == 'campaign_list':
            query = query.where(Campaign.id.in_([UUID(i) for i in context_hint['campaign_ids']]))
        elif context_hint['kind'] == 'segment':
            query = query.where(Campaign.segment_revision_id == UUID(context_hint['revision_id']))
    # Bound expensive attribution work before processing reports, not just output size.
    ids_with_sends = select(CampaignDelivery.campaign_id).where(CampaignDelivery.dataset_id == dataset_id,
        CampaignDelivery.status == 'SENT', CampaignDelivery.sent_at >= period.start, CampaignDelivery.sent_at < period.end)
    rows = session.scalars(query.where(Campaign.id.in_(ids_with_sends)).order_by(Campaign.id).limit(101)).all()
    if len(rows) > 100:
        raise AppError('AI_COMPARE_TOO_BROAD', '비교할 캠페인이 많습니다. 채널·세그먼트·기간을 좁혀주세요.', 422)
    cutoff = datetime.now(timezone.utc)
    finished = dict(session.execute(select(CampaignRun.campaign_id, func.max(CampaignRun.finished_at)).where(
        CampaignRun.dataset_id == dataset_id, CampaignRun.campaign_id.in_([r.id for r in rows]),
        CampaignRun.status == 'COMPLETED').group_by(CampaignRun.campaign_id)).all()) if rows else {}
    reports = []
    for campaign in rows:
        report = campaign_performance(session, dataset_id, campaign.id, period.start, period.end, cutoff)
        total = report['totals']
        reports.append({'campaign_id': str(campaign.id), 'name': campaign.name, 'channel': campaign.channel,
            'sent_count': total['sent_customers'], 'conversion_rate': total['conversion_rate']['value'],
            'click_rate': total['click_rate']['value'], 'revenue': total['revenue'],
            'completed_at': finished.get(campaign.id)})
    valid = [r for r in reports if r[parsed.sort] is not None]
    valid.sort(key=lambda r: Decimal(str(r[parsed.sort])), reverse=parsed.order == 'desc')
    ordered = valid + [r for r in reports if r[parsed.sort] is None]
    return {'campaigns': ordered[:parsed.limit], 'total_matched': len(reports),
        'from': period.start, 'to': period.end, 'reference_at': cutoff, 'sort': parsed.sort, 'order': parsed.order}
