from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import create_app
from app.core.config import Settings
from app.models.campaigns import Campaign, CampaignVariant
from app.models.datasets import Dataset
from app.schemas.segments import SegmentWrite
from app.services.segments import save
from scripts.seed_demo import seed_demo

pytestmark = pytest.mark.postgres


@pytest.fixture
def context(database):
    reference = datetime(2026,9,19,tzinfo=timezone.utc)
    with database.sessions.begin() as session:
        dataset,_ = seed_demo(session,seed=42,reference_at=reference)
        dataset_id = dataset.id
    with database.sessions() as session:
        segment = save(session,SegmentWrite(dataset_id=dataset_id,name='Target',condition={'field':'order_count','comparison':'GTE','value':1},reference_at=reference),uuid4())
    payload = dict(dataset_id=str(dataset_id),segment_revision_id=str(segment['revision_id']),name='Campaign',objective='Repeat purchase',channel='EMAIL',benefit='Coupon',brand_tone='Friendly',primary_kpi='conversion_rate',target_value='5.00',variants=[dict(variant_name=n,subject='Hello',body='Welcome',hypothesis='Benefit' if n=='A' else 'Urgency',allocation_bp=5000) for n in ['A','B']])
    app = create_app(Settings(_env_file=None,database_url=None)); app.state.database = database
    with TestClient(app) as client: yield client,payload


def test_campaign_create_update_conflict_and_scope(context,database):
    client,payload = context
    response = client.post('/api/v1/campaigns',json=payload)
    assert response.status_code == 201,response.text
    row = response.json(); path = '/api/v1/campaigns/'+row['id']
    assert row['status'] == 'DRAFT' and row['target_value'] == '5.00'
    assert client.get(path,params={'dataset_id':payload['dataset_id']}).json()['variants'] == row['variants']
    update = {**payload,'version':1,'name':'Changed'}
    changed = client.put(path,json=update)
    assert changed.status_code == 200,changed.text
    assert changed.json()['version'] == 2
    assert [v['id'] for v in changed.json()['variants']] == [v['id'] for v in row['variants']]
    assert client.put(path,json=update).status_code == 409
    with database.sessions.begin() as session:
        other = Dataset(name='Other'); session.add(other); session.flush(); other_id=str(other.id)
    assert client.post('/api/v1/campaigns',json={**payload,'dataset_id':other_id}).status_code == 404
    assert client.get(path,params={'dataset_id':other_id}).status_code == 404
    assert client.get('/api/v1/campaigns',params={'dataset_id':payload['dataset_id']}).json()['total'] == 1


def test_campaign_validation_and_channels(context,database):
    client,payload=context
    bad = [{**payload,'variants':[{**v,'allocation_bp':4000} for v in payload['variants']]},
           {**payload,'variants':[{**v,'body':' '} for v in payload['variants']]},
           {**payload,'variants':[{**v,'body':'{{customer.name}}'} for v in payload['variants']]},
           {**payload,'target_value':'101'}, {**payload,'planned_at':'2026-09-19T00:00:00'}]
    for data in bad: assert client.post('/api/v1/campaigns',json=data).status_code == 422
    for channel in ['PUSH','SMS']:
        data={**payload,'channel':channel,'variants':[{**v,'subject':'' if channel=='SMS' else 'Hello'} for v in payload['variants']]}
        assert client.post('/api/v1/campaigns',json=data).status_code == 201
    with database.sessions() as session: assert session.scalar(select(func.count()).select_from(Campaign)) == 2


def test_campaign_audit_failure_rolls_back(context,database,monkeypatch):
    from app.services import campaigns
    from app.schemas.campaign import CampaignWrite
    client,payload=context
    def fail(*args,**kwargs): raise RuntimeError('audit')
    monkeypatch.setattr(campaigns,'record_change',fail)
    with database.sessions() as session:
        with pytest.raises(RuntimeError): campaigns.save(session,CampaignWrite.model_validate(payload),uuid4())
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Campaign)) == 0
        assert session.scalar(select(func.count()).select_from(CampaignVariant)) == 0


def test_campaign_archive_removes_it_from_public_list(context,database):
    client,payload=context
    created=client.post('/api/v1/campaigns',json=payload).json()
    response=client.request('DELETE',f"/api/v1/campaigns/{created['id']}",json={'dataset_id':payload['dataset_id'],'version':created['version']})
    assert response.status_code==200,response.text
    assert response.json()['archived'] is True
    assert client.get('/api/v1/campaigns',params={'dataset_id':payload['dataset_id']}).json()['total']==0
    assert client.get(f"/api/v1/campaigns/{created['id']}",params={'dataset_id':payload['dataset_id']}).status_code==404
    assert client.request('DELETE',f"/api/v1/campaigns/{created['id']}",json={'dataset_id':payload['dataset_id'],'version':created['version']}).status_code==404
