from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4, UUID
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import create_app
from app.core.config import Settings
from app.schemas.segments import SegmentWrite
from app.services.segments import save
from app.workers.runner import run_once
from app.models.campaigns import CampaignDelivery, CampaignEvent, CampaignRun, ValidationRecipient, ValidationRun
from app.models.customers import Customer, CustomerChannel, Order
from scripts.seed_demo import seed_demo

pytestmark=pytest.mark.postgres

@pytest.fixture
def approved_campaign(database):
    reference=datetime(2026,9,19,tzinfo=timezone.utc)
    with database.sessions.begin() as session:
        dataset,_=seed_demo(session,seed=91,reference_at=reference); dataset_id=dataset.id
    with database.sessions() as session:
        segment=save(session,SegmentWrite(dataset_id=dataset_id,name='구매 고객',condition={'field':'order_count','comparison':'GTE','value':1},reference_at=reference),uuid4())
    app=create_app(Settings(_env_file=None,database_url=None)); app.state.database=database
    payload={'dataset_id':str(dataset_id),'segment_revision_id':str(segment['revision_id']),'name':'모의 발송 캠페인','objective':'재구매',
        'channel':'EMAIL','benefit':'15% 할인 쿠폰','brand_tone':'다정하게','primary_kpi':'conversion_rate','target_value':'5.00',
        'variants':[{'variant_name':name,'subject':f'{name}안','body':'15% 할인 쿠폰으로 둘러보세요.','hypothesis':name,'allocation_bp':5000} for name in ('A','B')]}
    with TestClient(app) as client:
        campaign=client.post('/api/v1/campaigns',json=payload).json(); base=f"/api/v1/campaigns/{campaign['id']}"
        run=client.post(base+'/validate',json={'dataset_id':str(dataset_id),'campaign_version':1,'reference_at':reference.isoformat()}).json()
        requested=client.post(base+'/request-approval',json={'dataset_id':str(dataset_id),'campaign_version':1,'validation_run_id':run['id']}).json()
        approved=client.post(base+'/approve',json={'dataset_id':str(dataset_id),'campaign_version':2,'approval_id':requested['approval']['id']}).json()['campaign']
        yield client,dataset_id,approved,run

def test_simulate_send_is_idempotent_and_worker_results_are_stable(approved_campaign,database):
    client,dataset_id,campaign,validation=approved_campaign; path=f"/api/v1/campaigns/{campaign['id']}/simulate-send"
    body={'dataset_id':str(dataset_id),'campaign_version':campaign['version']}; headers={'Idempotency-Key':'demo-run-1'}
    assert client.post(path,json=body).status_code==422
    first=client.post(path,json=body,headers=headers)
    assert first.status_code==202,first.text
    repeated=client.post(path,json=body,headers=headers)
    assert repeated.status_code==202 and repeated.json()['id']==first.json()['id']
    assert client.post(path,json={**body,'campaign_version':campaign['version']+1},headers=headers).status_code==409
    assert client.post(path,json=body,headers={'Idempotency-Key':'demo-run-2'}).status_code==409
    running=client.get(f"/api/v1/campaigns/{campaign['id']}",params={'dataset_id':str(dataset_id)}).json()
    blocked=client.request('DELETE',f"/api/v1/campaigns/{campaign['id']}",json={'dataset_id':str(dataset_id),'version':running['version']})
    assert blocked.status_code==409 and blocked.json()['error']['code']=='CAMPAIGN_RUNNING'
    with database.sessions() as session:
        cached_before=session.execute(select(func.sum(Customer.order_count),func.sum(Customer.total_purchase_amount)).where(Customer.dataset_id==dataset_id)).one()
    assert run_once(database,Settings(_env_file=None),None) is True
    result=client.get(f"/api/v1/campaigns/{campaign['id']}/runs/{first.json()['id']}",params={'dataset_id':str(dataset_id)})
    assert result.status_code==200,result.text
    data=result.json(); assert data['status']=='COMPLETED' and data['delivery_counts']['RESERVED']==0
    assert data['sent_count']+data['failed_count']==data['reserved_count']
    assert sum(data['failure_summary'].values())==data['excluded_count']+data['failed_count']
    assert sum(row['sent'] for row in data['variant_summary'])==data['sent_count']
    assert sum(row['failed'] for row in data['variant_summary'])==data['failed_count']
    assert data['event_summary']['DELIVERED']==data['sent_count']
    with database.sessions() as session:
        deliveries=session.scalars(select(CampaignDelivery).where(CampaignDelivery.run_id==UUID(data['id']))).all()
        assigned=[row for row in deliveries if row.status in ('SENT','FAILED')]
        assert len({row.customer_id for row in deliveries})==len(deliveries)==data['initial_count']
        assert all(row.variant_id for row in assigned) and len({row.variant_id for row in assigned})==2
        assert session.scalar(select(func.count()).select_from(CampaignEvent).where(CampaignEvent.run_id==UUID(data['id']),CampaignEvent.event_type=='DELIVERED'))==data['sent_count']
        assert session.scalar(select(func.count()).select_from(Order).where(Order.dataset_id==dataset_id,Order.source=='SIMULATED'))>=1
        cached_after=session.execute(select(func.sum(Customer.order_count),func.sum(Customer.total_purchase_amount)).where(Customer.dataset_id==dataset_id)).one()
        assert cached_after==cached_before

def test_execution_recheck_excludes_revoked_consent(approved_campaign,database):
    client,dataset_id,campaign,validation=approved_campaign
    with database.sessions.begin() as session:
        customer_id=session.scalar(select(ValidationRecipient.customer_id).where(ValidationRecipient.validation_run_id==UUID(validation['id']),ValidationRecipient.eligible.is_(True)).limit(1))
        channel=session.scalar(select(CustomerChannel).where(CustomerChannel.dataset_id==dataset_id,CustomerChannel.customer_id==customer_id,CustomerChannel.channel=='EMAIL'))
        channel.consent=False
    response=client.post(f"/api/v1/campaigns/{campaign['id']}/simulate-send",json={'dataset_id':str(dataset_id),'campaign_version':campaign['version']},headers={'Idempotency-Key':'revoked-consent'})
    assert response.status_code==202,response.text
    with database.sessions() as session:
        delivery=session.scalar(select(CampaignDelivery).where(CampaignDelivery.run_id==UUID(response.json()['id']),CampaignDelivery.customer_id==customer_id))
        assert delivery.status=='EXCLUDED' and delivery.exclusion_reason=='NO_CONSENT'

def test_approved_snapshot_can_run_after_validation_window(approved_campaign,database):
    client,dataset_id,campaign,validation=approved_campaign
    with database.sessions.begin() as session:
        row=session.get(ValidationRun,UUID(validation['id']))
        row.expires_at=datetime(2020,1,1,tzinfo=timezone.utc)
    response=client.post(f"/api/v1/campaigns/{campaign['id']}/simulate-send",
        json={'dataset_id':str(dataset_id),'campaign_version':campaign['version']},headers={'Idempotency-Key':'approved-after-window'})
    assert response.status_code==202,response.text

def test_approved_campaign_can_be_archived_without_deleting_history(approved_campaign):
    client,dataset_id,campaign,_=approved_campaign
    response=client.request('DELETE',f"/api/v1/campaigns/{campaign['id']}",json={'dataset_id':str(dataset_id),'version':campaign['version']})
    assert response.status_code==200,response.text
    assert response.json()['archived'] is True
    rows=client.get('/api/v1/campaigns',params={'dataset_id':str(dataset_id)}).json()['items']
    assert all(row['id']!=campaign['id'] for row in rows)

def test_performance_counts_distinct_customers_and_reports_simulation(approved_campaign,database):
    client,dataset_id,campaign,_=approved_campaign
    sent=client.post(f"/api/v1/campaigns/{campaign['id']}/simulate-send",json={'dataset_id':str(dataset_id),'campaign_version':campaign['version']},headers={'Idempotency-Key':'performance-run'})
    assert sent.status_code==202,sent.text
    assert run_once(database,Settings(_env_file=None),None) is True
    now=datetime.now(timezone.utc);params={'dataset_id':str(dataset_id),'from':(now-timedelta(days=1)).isoformat(),'to':(now+timedelta(days=1)).isoformat()}
    first=client.get(f"/api/v1/campaigns/{campaign['id']}/performance",params=params)
    assert first.status_code==200,first.text
    result=first.json();totals=result['totals']
    assert totals['delivered_customers']==totals['sent_customers']>0
    assert totals['conversion_customers']>0 and Decimal(totals['revenue'])>0
    assert len(result['variants'])==2 and result['experiment']['status']=='HOLD'
    assert result['observation']['complete'] is True and result['observation']['window_days']==0
    assert 'OBSERVATION_OPEN' not in result['experiment']['reasons']
    assert result['incremental_revenue']['status']=='not_available' and result['contains_simulated_data'] is True
    with database.sessions.begin() as session:
        original=session.scalar(select(CampaignEvent).where(CampaignEvent.run_id==UUID(sent.json()['id']),CampaignEvent.event_type=='OPEN').limit(1))
        if original:
            session.add(CampaignEvent(dataset_id=original.dataset_id,campaign_id=original.campaign_id,run_id=original.run_id,delivery_id=original.delivery_id,
                customer_id=original.customer_id,variant_id=original.variant_id,order_id=None,external_id=f'duplicate-open-{uuid4()}',event_type='OPEN',event_at=original.event_at+timedelta(seconds=1),source='SIMULATED'))
    repeated=client.get(f"/api/v1/campaigns/{campaign['id']}/performance",params=params).json()
    assert repeated['totals']['open_customers']==totals['open_customers']
    summary=client.get('/api/v1/reports/summary',params=params).json()
    assert summary['campaign_count']==1 and summary['contains_simulated_data'] is True
    export=client.get('/api/v1/reports/export',params=params)
    assert export.status_code==200 and export.content.startswith(b'\xef\xbb\xbf') and b'campaign_name' in export.content
