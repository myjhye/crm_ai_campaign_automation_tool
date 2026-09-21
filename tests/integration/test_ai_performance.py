from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func

from test_simulations import approved_campaign
from app.ai.provider import MockProvider
from app.ai.orchestrator import confirm
from app.core.config import Settings
from app.models.ai import AIActionProposal, AIExecutionLog
from app.models.campaigns import Campaign, PolicySetting, CampaignEvent
from app.workers.runner import run_once

pytestmark=pytest.mark.postgres


@pytest.fixture
def completed(approved_campaign,database):
    client,did,campaign,_=approved_campaign
    client.app.state.ai_provider=MockProvider()
    client.app.state.settings=Settings(_env_file=None,ai_mode='mock')
    response=client.post(f"/api/v1/campaigns/{campaign['id']}/simulate-send",json={'dataset_id':str(did),'campaign_version':campaign['version']},headers={'Idempotency-Key':'ai-performance'})
    assert response.status_code==202,response.text
    assert run_once(database,Settings(_env_file=None),None)
    now=datetime.now(timezone.utc)
    query={'dataset_id':str(did),'campaign_id':campaign['id'],'from':(now-timedelta(days=1)).isoformat(),'to':(now+timedelta(days=1)).isoformat()}
    return client,query


def analyze(client,query):
    response=client.post('/api/v1/ai/performance-analysis',json=query)
    assert response.status_code==200,response.text
    return response.json()['data']


def test_evidence_and_atomic_idempotent_followup(completed,database):
    client,query=completed; data=analyze(client,query)
    assert any('합성' in text for text in data['limitations'])
    for fact in data['facts']: assert fact['value']==data['metric_refs'][fact['metric_id']]['value']
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Campaign))==1
    path=f"/api/v1/ai/actions/{data['proposal']['proposal_id']}/confirm"
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:client.post(path,json={'dataset_id':query['dataset_id']}),range(2)))
    assert all(r.status_code==200 for r in responses),[r.text for r in responses]
    assert responses[0].json()['id']==responses[1].json()['id']
    saved=responses[0].json()
    assert saved['status']=='DRAFT' and saved['id']!=query['campaign_id']
    assert saved['benefit']==data['proposal']['draft']['benefit']
    assert saved['planned_at'] is None
    chat=client.post('/api/v1/ai/chat',json={k:v for k,v in {**query,'campaign_id':None,'analysis_campaign_id':query['campaign_id'],
        'reference_at':datetime.now(timezone.utc).isoformat(),'prompt':'성과를 분석해줘'}.items() if v is not None})
    assert chat.status_code==200,chat.text
    assert chat.json()['result_type']=='performance_analysis'
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Campaign))==2
        log=session.scalar(select(AIExecutionLog).where(AIExecutionLog.tool_name=='analyze_campaign'))
        assert log.status=='SUCCESS' and log.prompt_version=='ai-d-3'


@pytest.mark.parametrize('kind',['number','device','action','tool'])
def test_untrusted_output_never_creates_proposal(completed,database,kind):
    client,query=completed
    class Invalid(MockProvider):
        def plan(self,prompt,context):
            assert 'name' not in context['performance'] and 'customers' not in context['performance']
            name,args,tokens=super().plan(prompt,context)
            if kind=='number':args['facts'][0]['value']='999999'
            if kind=='device':args['facts'][0]['metric_id']='mobile.exit_rate'
            if kind=='action':args['recommended_actions']=['SEND_NOW']
            if kind=='tool':name='approve_campaign'
            return name,args,tokens
    client.app.state.ai_provider=Invalid()
    response=client.post('/api/v1/ai/performance-analysis',json=query)
    assert response.status_code==502,response.text
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(AIActionProposal))==0
        assert session.scalar(select(AIExecutionLog.status).where(AIExecutionLog.tool_name=='analyze_campaign'))=='FAILED'


@pytest.mark.parametrize('change',['expired','hash','source','policy','evidence'])
def test_stale_proposals_cannot_be_saved(completed,database,change):
    client,query=completed; data=analyze(client,query); pid=UUID(data['proposal']['proposal_id'])
    with database.sessions.begin() as session:
        proposal=session.get(AIActionProposal,pid)
        if change=='expired':proposal.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        if change=='hash':proposal.payload_hash='invalid'
        if change=='source':session.get(Campaign,UUID(query['campaign_id'])).version+=1
        if change=='policy':session.add(PolicySetting(dataset_id=UUID(query['dataset_id']),version=2))
        if change=='evidence':
            event=session.scalar(select(CampaignEvent).where(CampaignEvent.campaign_id==UUID(query['campaign_id']),CampaignEvent.event_type=='DELIVERED').limit(1))
            session.delete(event)
    response=client.post(f'/api/v1/ai/actions/{pid}/confirm',json={'dataset_id':query['dataset_id']})
    assert response.status_code==409,response.text
    with database.sessions() as session: assert session.scalar(select(func.count()).select_from(Campaign))==1


def test_followup_audit_failure_rolls_back(completed,database,monkeypatch):
    from app.services import campaigns
    client,query=completed;data=analyze(client,query);pid=UUID(data['proposal']['proposal_id'])
    def fail(*args,**kwargs):raise RuntimeError('audit unavailable')
    monkeypatch.setattr(campaigns,'record_change',fail)
    with database.sessions() as session:
        with pytest.raises(RuntimeError):confirm(session,pid,UUID(query['dataset_id']),uuid4())
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Campaign))==1
        assert session.get(AIActionProposal,pid).confirmed_at is None


def test_scope_empty_period_and_model_time_conflict(completed,database):
    client,query=completed
    assert client.post('/api/v1/ai/performance-analysis',json={**query,'dataset_id':str(uuid4())}).status_code==404
    assert client.post('/api/v1/ai/performance-analysis',json={**query,'from':'2020-01-01T00:00:00Z','to':'2020-02-01T00:00:00Z'}).status_code==422
    class Mutating(MockProvider):
        def plan(self,prompt,context):
            with database.sessions.begin() as session:session.get(Campaign,UUID(query['campaign_id'])).version+=1
            return super().plan(prompt,context)
    client.app.state.ai_provider=Mutating()
    assert client.post('/api/v1/ai/performance-analysis',json=query).status_code==409
