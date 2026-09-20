from datetime import datetime,timezone,timedelta
from uuid import uuid4,UUID
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select,func
from fastapi.testclient import TestClient
from app.main import create_app
from app.core.config import Settings
from app.services.segments import save
from app.schemas.segments import SegmentWrite
from app.models.campaigns import Campaign
from app.models.ai import AIActionProposal
from app.ai.provider import MockProvider
from scripts.seed_demo import seed_demo

pytestmark=pytest.mark.postgres


def test_guided_setup_skips_llm_clarification_and_locks_settings(context):
    client,app,base,brief=context
    class GuidedProvider(MockProvider):
        def plan(self,prompt,context):
            assert 'brief_schema' not in context
            assert context['campaign']['brand_tone']=='다정하고 편안하게'
            assert 'A안: 혜택 강조' in prompt and 'B안: 관계 강조' in prompt
            return super().plan(prompt,context)
    app.state.ai_provider=GuidedProvider()
    setup={'segment_revision_id':brief['segment_revision_id'],'benefit':'15% 할인 쿠폰','target_value':'8'}
    response=client.post('/api/v1/ai/campaign-plan',json={**base,'campaign_setup':setup})
    assert response.status_code==200,response.text
    data=response.json()['data']
    assert data['benefit']==setup['benefit'] and data['target_value']=='8'
    assert data['primary_kpi']=='conversion_rate' and data['channel']=='EMAIL'
    assert data['name']=='Target · 재구매 유도'
    for override in [{'a_focus':'관계 강조'},{'target_value':'101'},{'benefit':''}]:
        response=client.post('/api/v1/ai/campaign-plan',json={**base,'campaign_setup':{**setup,**override}})
        assert response.status_code==422


def test_whole_plan_and_unknown_target(context):
    import json
    client,app,base,brief=context
    class Planner(MockProvider):
        invalid=False
        def plan(self,prompt,ctx):
            if 'brief_schema' in ctx:
                value={**brief,'segment_revision_id':str(uuid4()) if self.invalid else ctx['segments'][0]['id']}
                return 'plan_campaign',{'question':'','brief_json':json.dumps(value)},0
            return super().plan(prompt,ctx)
    provider=Planner();app.state.ai_provider=provider
    response=client.post('/api/v1/ai/campaign-plan',json={**base,'prompt':'Email campaign with 10% coupon'})
    assert response.status_code==200,response.text
    assert response.json()['data']['variants'][0]['allocation_bp']==5000
    assert response.json()['segment_name']=='Target'
    response=client.post('/api/v1/ai/campaign-plan',json=base)
    assert response.json()['result_type']=='clarification'
    provider.invalid=True
    response=client.post('/api/v1/ai/campaign-plan',json=base)
    assert response.status_code==502


def test_invalid_copy_is_regenerated_once(context):
    client,app,base,brief=context
    class RepairProvider(MockProvider):
        calls=0
        def plan(self,prompt,context):
            self.calls+=1
            name,args,tokens=super().plan(prompt,context)
            if self.calls==1:
                args['variants'][0]['body']='unrelated copy'
            else:
                assert 'validation_feedback' in context
            return name,args,tokens
    provider=RepairProvider()
    app.state.ai_provider=provider
    response=client.post('/api/v1/ai/campaign-draft',json={**base,'campaign_brief':brief})
    assert response.status_code==200,response.text
    assert provider.calls==2

@pytest.fixture
def context(database):
    ref=datetime(2026,9,19,tzinfo=timezone.utc)
    with database.sessions.begin() as session:
        dataset,_=seed_demo(session,seed=42,reference_at=ref); did=dataset.id
    with database.sessions() as session:
        segment=save(session,SegmentWrite(dataset_id=did,name='Target',condition={'field':'order_count','comparison':'GTE','value':1},reference_at=ref),uuid4())
    app=create_app(Settings(_env_file=None,database_url=None,ai_mode='mock'));app.state.database=database
    base={'dataset_id':str(did),'from':'2026-08-19T00:00:00Z','to':ref.isoformat(),'reference_at':ref.isoformat(),'prompt':'Generate copy'}
    brief={'segment_revision_id':str(segment['revision_id']),'name':'Campaign','objective':'Repeat purchase','channel':'EMAIL','benefit':'10% coupon','brand_tone':'Friendly'}
    with TestClient(app) as client:yield client,app,base,brief


def test_campaign_proposal_confirm_and_stale_copy(context,database):
    client,app,base,brief=context
    result=client.post('/api/v1/ai/campaign-draft',json={**base,'campaign_brief':brief})
    assert result.status_code==200,result.text
    data=result.json()['data']; path=f"/api/v1/ai/actions/{data['proposal_id']}/confirm"
    with database.sessions() as session:assert session.scalar(select(func.count()).select_from(Campaign))==0
    def apply():return client.post(path,json={'dataset_id':base['dataset_id']})
    with ThreadPoolExecutor(max_workers=2) as pool: responses=list(pool.map(lambda _:apply(),range(2)))
    assert all(r.status_code==200 for r in responses),[r.text for r in responses]
    created=responses[0].json();assert responses[1].json()['id']==created['id']
    copy_request={**base,'campaign_id':created['id'],'campaign_version':created['version']}
    response=client.post('/api/v1/ai/copy-variants',json=copy_request)
    assert response.status_code==200,response.text
    proposal=response.json()['data']['proposal_id']
    with database.sessions.begin() as session:session.get(Campaign,UUID(created['id'])).version+=1
    assert client.post(f'/api/v1/ai/actions/{proposal}/confirm',json={'dataset_id':base['dataset_id']}).status_code==409
    copy_request['campaign_version']=2
    response=client.post('/api/v1/ai/chat',json=copy_request)
    assert response.status_code==200,response.text
    proposal=response.json()['data']['proposal_id']
    applied=client.post(f'/api/v1/ai/actions/{proposal}/confirm',json={'dataset_id':base['dataset_id']})
    assert applied.status_code==200,applied.text
    assert applied.json()['version']==3


def test_invented_benefit_expiry_and_atomicity(context,database,monkeypatch):
    client,app,base,brief=context
    class BadProvider(MockProvider):
        def plan(self,prompt,context):
            name,args,tokens=super().plan(prompt,context)
            args['variants'][0]['body']+=' 90% off'
            return name,args,tokens
    app.state.ai_provider=BadProvider()
    assert client.post('/api/v1/ai/chat',json={**base,'campaign_brief':brief}).status_code==502
    with database.sessions() as session:assert session.scalar(select(func.count()).select_from(AIActionProposal))==0
    app.state.ai_provider=MockProvider()
    data=client.post('/api/v1/ai/chat',json={**base,'campaign_brief':brief}).json()['data']
    from app.ai.orchestrator import confirm
    from app.services import campaigns
    def fail(*args,**kwargs):raise RuntimeError('audit')
    monkeypatch.setattr(campaigns,'record_change',fail)
    with database.sessions() as session:
        with pytest.raises(RuntimeError):confirm(session,UUID(data['proposal_id']),UUID(base['dataset_id']),uuid4())
    with database.sessions.begin() as session:
        assert session.scalar(select(func.count()).select_from(Campaign))==0
        row=session.get(AIActionProposal,UUID(data['proposal_id']));assert row.confirmed_at is None
        row.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
    assert client.post(f"/api/v1/ai/actions/{data['proposal_id']}/confirm",json={'dataset_id':base['dataset_id']}).status_code==409


@pytest.mark.parametrize('channel',['EMAIL','PUSH','SMS'])
def test_channels(context,channel):
    client,app,base,brief=context
    response=client.post('/api/v1/ai/chat',json={**base,'campaign_brief':{**brief,'channel':channel}})
    assert response.status_code==200,response.text
    if channel=='SMS':assert all(v['subject']=='' for v in response.json()['data']['variants'])


def test_edited_proposal_gets_new_hash_and_old_card_expires(context):
    client,app,base,brief=context
    data=client.post('/api/v1/ai/chat',json={**base,'campaign_brief':brief}).json()['data']
    copies=[{key:v[key] for key in ('variant_name','subject','body','hypothesis')} for v in data['variants']]
    copies[0]['subject']='Edited title'
    revised=client.post(f"/api/v1/ai/actions/{data['proposal_id']}/revise",json={'dataset_id':base['dataset_id'],'variants':copies})
    assert revised.status_code==200,revised.text
    assert revised.json()['proposal_id']!=data['proposal_id']
    assert client.post(f"/api/v1/ai/actions/{data['proposal_id']}/confirm",json={'dataset_id':base['dataset_id']}).status_code==409
    applied=client.post(f"/api/v1/ai/actions/{revised.json()['proposal_id']}/confirm",json={'dataset_id':base['dataset_id']})
    assert applied.status_code==200,applied.text
    assert applied.json()['variants'][0]['subject']=='Edited title'
