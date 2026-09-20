from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Settings
from app.schemas.segments import SegmentWrite
from app.services.segments import save
from scripts.seed_demo import seed_demo

pytestmark=pytest.mark.postgres

@pytest.fixture
def campaign_context(database):
    reference=datetime(2026,9,19,tzinfo=timezone.utc)
    with database.sessions.begin() as session:
        dataset,_=seed_demo(session,seed=74,reference_at=reference); dataset_id=dataset.id
    with database.sessions() as session:
        segment=save(session,SegmentWrite(dataset_id=dataset_id,name='전체 구매 고객',condition={'field':'order_count','comparison':'GTE','value':1},reference_at=reference),uuid4())
    app=create_app(Settings(_env_file=None,database_url=None)); app.state.database=database
    payload={'dataset_id':str(dataset_id),'segment_revision_id':str(segment['revision_id']),'name':'검수 캠페인','objective':'재구매',
        'channel':'EMAIL','benefit':'15% 할인 쿠폰','brand_tone':'다정하게','primary_kpi':'conversion_rate','target_value':'5.00',
        'variants':[{'variant_name':name,'subject':'다시 만나요','body':'15% 할인 쿠폰을 확인해보세요.','hypothesis':'혜택' if name=='A' else '관계','allocation_bp':5000} for name in ('A','B')]}
    with TestClient(app) as client:
        campaign=client.post('/api/v1/campaigns',json=payload).json()
        yield client,payload,campaign,reference

def test_validate_request_approve_and_resume(campaign_context):
    client,payload,campaign,reference=campaign_context; base=f"/api/v1/campaigns/{campaign['id']}"
    validation=client.post(base+'/validate',json={'dataset_id':payload['dataset_id'],'campaign_version':1,'reference_at':reference.isoformat()})
    assert validation.status_code==201,validation.text
    run=validation.json(); assert run['initial_count']==run['eligible_count']+run['excluded_count'] and run['eligible_count']>0
    assert sum(rule['primary_count'] for rule in run['rules'])==run['excluded_count']
    requested=client.post(base+'/request-approval',json={'dataset_id':payload['dataset_id'],'campaign_version':1,'validation_run_id':run['id']})
    assert requested.status_code==200,requested.text
    body=requested.json(); assert body['campaign']['status']=='REVIEW' and body['campaign']['version']==2
    approved=client.post(base+'/approve',json={'dataset_id':payload['dataset_id'],'campaign_version':2,'approval_id':body['approval']['id'],'comment':'확인 완료'})
    assert approved.status_code==200,approved.text
    assert approved.json()['campaign']['status']=='APPROVED'
    assert client.post(base+'/approve',json={'dataset_id':payload['dataset_id'],'campaign_version':2,'approval_id':body['approval']['id']}).status_code==409
    resumed=client.post(base+'/resume-editing',json={'dataset_id':payload['dataset_id'],'campaign_version':3})
    assert resumed.status_code==200 and resumed.json()['status']=='DRAFT' and resumed.json()['version']==4

def test_policy_change_invalidates_validation(campaign_context):
    client,payload,campaign,reference=campaign_context; base=f"/api/v1/campaigns/{campaign['id']}"
    run=client.post(base+'/validate',json={'dataset_id':payload['dataset_id'],'campaign_version':1,'reference_at':reference.isoformat()}).json()
    policy=client.get('/api/v1/policy-settings',params={'dataset_id':payload['dataset_id']}).json()
    changed=client.put('/api/v1/policy-settings',json={**policy,'daily_limit':2})
    assert changed.status_code==200,changed.text
    response=client.post(base+'/request-approval',json={'dataset_id':payload['dataset_id'],'campaign_version':1,'validation_run_id':run['id']})
    assert response.status_code==409 and response.json()['error']['code']=='VALIDATION_EXPIRED'

def test_expired_coupon_blocks_campaign(campaign_context):
    client,payload,campaign,reference=campaign_context
    update={**payload,'version':1,'coupon_expires_at':'2026-09-18T00:00:00Z'}
    campaign=client.put(f"/api/v1/campaigns/{campaign['id']}",json=update).json()
    run=client.post(f"/api/v1/campaigns/{campaign['id']}/validate",json={'dataset_id':payload['dataset_id'],'campaign_version':2,'reference_at':reference.isoformat()}).json()
    assert run['passed'] is False and run['blockers'][0]['rule_code']=='EXPIRED_COUPON'

def test_ai_validation_tool_records_result_without_approval(campaign_context,database):
    from sqlalchemy import select
    from app.models.datasets import AuditLog
    from app.models.campaigns import ValidationRun
    client,payload,campaign,reference=campaign_context
    body={'dataset_id':payload['dataset_id'],'from':'2026-08-19T00:00:00Z','to':reference.isoformat(),
        'reference_at':reference.isoformat(),'prompt':'선택한 캠페인을 정책 검수해줘',
        'validation_campaign_id':campaign['id'],'validation_campaign_version':campaign['version']}
    response=client.post('/api/v1/ai/chat',json=body)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['result_type']=='campaign_validation' and result['data']['campaign_id']==campaign['id']
    assert result['data']['initial_count']==result['data']['eligible_count']+result['data']['excluded_count']
    review=client.get(f"/api/v1/campaigns/{campaign['id']}/review",params={'dataset_id':payload['dataset_id']}).json()
    assert review['campaign']['status']=='DRAFT' and review['approval'] is None
    with database.sessions() as session:
        assert session.scalar(select(ValidationRun).where(ValidationRun.id==result['data']['id'])) is not None
        audit=session.scalar(select(AuditLog).where(AuditLog.resource_id==campaign['id'],AuditLog.action=='CAMPAIGN_VALIDATED').order_by(AuditLog.created_at.desc()))
        assert audit.actor_type=='AI'
