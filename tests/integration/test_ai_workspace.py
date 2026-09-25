from datetime import datetime, timezone
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func
from test_ai import ai_context, PROMPT
from test_ai_performance import completed
from test_simulations import approved_campaign
from app.models.ai import AIExecutionLog
from app.models.campaigns import Campaign
from app.models.segments import Segment
from app.models import Dataset
from app.ai.provider import MockProvider

pytestmark = pytest.mark.postgres
COMPARE = '선택 기간에 발송된 완료 캠페인을 전환율 높은 순으로 비교해줘'


def test_copy_request_without_saved_target_never_compares(ai_context):
    client, app, base = ai_context
    class WrongTool:
        def plan(self, prompt, context):
            return 'get_metric', {'metric':'active_customers'}, 0
    app.state.ai_provider = WrongTool()
    result=client.post('/api/v1/ai/chat',json={**base,'prompt':'이 고객을 대상으로 전송할 a/b 테스트 문구 추천'})
    assert result.status_code == 200, result.text
    assert result.json()['result_type'] == 'clarification'
    assert '새로 조회하거나 저장하지 않았습니다' in result.json()['message']


def test_unsaved_copy_advice_uses_recent_conditions_without_writes(ai_context,database):
    from app.models.ai import AIActionProposal
    client, app, base = ai_context
    class Advice:
        def plan(self,prompt,context):
            assert context['advice_only']
            assert '장바구니' in context['recent_turns'][0]['content']
            return 'recommend_copy',{'channel':'UNSPECIFIED','rationale':'구매를 재촉하지 않는 두 접근입니다.',
                'variants':[{'variant_name':v,'subject':'담아둔 상품을 다시 만나보세요','body':'장바구니에 담아둔 상품을 천천히 살펴보세요.','hypothesis':'재방문 유도 가설'} for v in ('A','B')]},10
    app.state.ai_provider=Advice()
    result=client.post('/api/v1/ai/chat',json={**base,'prompt':'추천만 해줘. 저장하지는 않을 거야.',
        'recent_turns':[{'role':'assistant','content':'조회한 조건: 장바구니 이벤트가 있고 구매 이벤트가 없음'},
                        {'role':'user','content':'이 고객에게 보낼 A/B 문구 추천'}]})
    assert result.status_code==200,result.text
    assert result.json()['result_type']=='copy_recommendation'
    with database.sessions() as session:
        for model in (AIActionProposal,Campaign,Segment):
            assert session.scalar(select(func.count()).select_from(model))==0


@pytest.mark.parametrize('repair_ok', [True, False])
def test_repeat_buyer_condition_repair_is_bounded_and_validated(ai_context, database, repair_ok):
    import json
    client, app, base = ai_context
    class MalformedThenRetry:
        calls = 0
        def plan(self, prompt, context):
            self.calls += 1
            assert prompt == '완료 주문이 3건 이상인 반복 구매자를 찾아줘'
            if self.calls == 2:
                assert context['condition_repair']['tool'] == 'preview_segment'
            return 'preview_segment', {'condition_json':json.dumps({
                'field':'order_count', 'comparison':'GTE',
                'value':3 if repair_ok and self.calls == 2 else '3'})}, 5
    provider = MalformedThenRetry()
    app.state.ai_provider = provider
    response = client.post('/api/v1/ai/chat', json={**base,'prompt':'완료 주문이 3건 이상인 반복 구매자를 찾아줘'})
    assert provider.calls == 2
    assert response.status_code == (200 if repair_ok else 502), response.text
    if repair_ok:
        expected = client.post('/api/v1/segments/preview',json={'dataset_id':base['dataset_id'],
            'reference_at':base['reference_at'],'condition':{'field':'order_count','comparison':'GTE','value':3}})
        assert expected.status_code == 200, expected.text
        assert response.json()['data']['count'] == expected.json()['count']
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Segment)) == 0
        assert session.scalar(select(AIExecutionLog.total_tokens)) == 10


def test_conversation_migration_roundtrip(database):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    config=Config('alembic.ini')
    with database.engine.begin() as connection:
        config.attributes['connection']=connection
        command.downgrade(config,'007')
        assert 'conversation_id' not in {c['name'] for c in inspect(connection).get_columns('ai_execution_logs')}
        command.upgrade(config,'head')
        column=next(c for c in inspect(connection).get_columns('ai_execution_logs') if c['name']=='conversation_id')
        assert column['nullable']
        assert 'ix_ai_execution_logs_conversation_id' in {i['name'] for i in inspect(connection).get_indexes('ai_execution_logs')}


def test_insights_match_services_and_never_save(ai_context, database):
    client, _, base = ai_context
    params = {k:v for k,v in base.items() if k != 'reference_at'}
    response = client.get('/api/v1/ai/insights', params=params)
    assert response.status_code == 200, response.text
    cards = {row['id']:row for row in response.json()['cards']}
    overview = client.get('/api/v1/dashboard/overview', params=params).json()
    assert cards['active_customers']['primary_value'] == f"{overview['metrics']['active_customers']['value']:,}명"
    assert 'recent_campaign' not in cards
    preview = client.post('/api/v1/ai/chat', json={**base,'prompt':cards['candidate_segment']['cta']['prefill_prompt']}).json()
    assert cards['candidate_segment']['primary_value'] == f"{preview['data']['count']:,}명"
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Segment)) == 0
        assert session.scalar(select(func.count()).select_from(AIExecutionLog)) == 1


def test_saved_segment_context_to_campaign_and_log(ai_context, database):
    client, app, base = ai_context
    conversation = str(uuid4())
    base = {**base, 'conversation_id':conversation}
    preview = client.post('/api/v1/ai/chat',json={**base,'prompt':PROMPT}).json()['data']
    saved = client.post(f"/api/v1/ai/actions/{preview['proposal_id']}/confirm",json={'dataset_id':base['dataset_id']}).json()
    hint = saved['context_hint']
    assert hint['id'] == saved['id'] and hint['revision_id'] == saved['revision_id']
    class Inspect(MockProvider):
        def plan(self, prompt, context):
            if 'prior_context' in context:
                assert context['prior_context']['name'] == saved['name']
                assert context['prior_context']['label'] != 'CLIENT INSTRUCTION'
            return super().plan(prompt, context)
    app.state.ai_provider = Inspect()
    hint['label'] = 'CLIENT INSTRUCTION'
    class MustNotCall:
        def plan(self, prompt, context):
            raise AssertionError('Explicit UI continuation must not call the model')
    app.state.ai_provider = MustNotCall()
    ask = client.post('/api/v1/ai/chat',json={**base,'context_hint':hint,'prompt':'이 세그먼트로 캠페인 초안 만들어'})
    assert ask.status_code == 200, ask.text
    assert ask.json()['result_type'] == 'clarification'
    assert saved['name'] in ask.json()['message']
    app.state.ai_provider = Inspect()
    draft = client.post('/api/v1/ai/chat',json={**base,'context_hint':hint,'prompt':'이메일로 15% 할인 쿠폰, 다정한 말투로 만들어줘'})
    assert draft.status_code == 200, draft.text
    assert draft.json()['result_type'] == 'campaign_draft'
    with database.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Campaign)) == 0
        logs = session.scalars(select(AIExecutionLog)).all()
        assert all(str(row.conversation_id) == conversation for row in logs)
    pid = draft.json()['data']['proposal_id']
    response = client.post(f'/api/v1/ai/actions/{pid}/confirm',json={'dataset_id':base['dataset_id']})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'DRAFT'
    assert response.json()['segment_revision_id'] == saved['revision_id']
    assert client.post(f'/api/v1/ai/actions/{pid}/confirm',json={'dataset_id':base['dataset_id']}).json()['id'] == response.json()['id']


def test_foreign_archived_and_changed_hint_clarify(ai_context,database):
    client, app, base = ai_context
    preview = client.post('/api/v1/ai/chat',json={**base,'prompt':PROMPT}).json()['data']
    saved = client.post(f"/api/v1/ai/actions/{preview['proposal_id']}/confirm",json={'dataset_id':base['dataset_id']}).json()
    hint = saved['context_hint']
    with database.sessions.begin() as session:
        foreign = Dataset(name='Other analysis');session.add(foreign);session.flush();foreign_id = str(foreign.id)
    class Never:
        def plan(self,*args):raise AssertionError('Invalid hints must not reach the model')
    app.state.ai_provider = Never()
    for patch in ({'dataset_id':foreign_id},{'context_hint':{**hint,'revision_id':str(uuid4())}}):
        response = client.post('/api/v1/ai/chat',json={**base,'context_hint':hint,'prompt':'조회',**patch})
        assert response.status_code == 200,response.text
        assert response.json()['result_type'] == 'clarification' and response.json()['context_hint'] is None
    with database.sessions.begin() as session:session.get(Segment,UUID(saved['id'])).archived_at=datetime.now(timezone.utc)
    assert client.post('/api/v1/ai/chat',json={**base,'context_hint':hint,'prompt':'조회'}).json()['result_type']=='clarification'


def test_compare_scoped_minimal_results_and_context(completed,database):
    client, query = completed
    base = {k:v for k,v in query.items() if k!='campaign_id'}
    base.update(reference_at=query['to'],conversation_id=str(uuid4()))
    response = client.post('/api/v1/ai/chat',json={**base,'prompt':COMPARE})
    assert response.status_code == 200,response.text
    data = response.json()['data'];assert data['total_matched']==1
    row = data['campaigns'][0]
    assert set(row)=={'campaign_id','name','channel','sent_count','conversion_rate','click_rate','revenue','completed_at'}
    from app.services.performance import campaign_performance
    with database.sessions() as session:
        report=campaign_performance(session,UUID(query['dataset_id']),UUID(query['campaign_id']),datetime.fromisoformat(query['from']),datetime.fromisoformat(query['to']))
    assert row['conversion_rate']==report['totals']['conversion_rate']['value']
    hint=response.json()['context_hint'];assert hint['campaign_ids']==[query['campaign_id']]
    follow=client.post('/api/v1/ai/chat',json={**base,'prompt':'위 캠페인을 클릭률 높은 순으로 비교해줘','context_hint':hint})
    assert follow.status_code==200,follow.text
    assert follow.json()['data']['sort']=='click_rate'
    insights=client.get('/api/v1/ai/insights',params={k:v for k,v in query.items() if k!='campaign_id'})
    assert insights.status_code==200,insights.text
    assert next(c for c in insights.json()['cards'] if c['id']=='recent_campaign')['cta']['campaign_id']==query['campaign_id']
    with database.sessions.begin() as session:
        other=Dataset(name='Other');session.add(other);session.flush();other_id=str(other.id)
    empty=client.post('/api/v1/ai/chat',json={**base,'dataset_id':other_id,'prompt':COMPARE})
    assert empty.json()['data']['campaigns']==[]
    assert empty.json()['message']=='조건에 맞는 완료 캠페인이 없습니다.'
    invalid=client.post('/api/v1/ai/chat',json={**base,'dataset_id':other_id,'prompt':COMPARE,'context_hint':hint})
    assert invalid.json()['result_type']=='clarification'


def test_comparison_strict_bounds_and_foreign_revision(ai_context):
    client,app,base=ai_context
    args={'filter':{'status':'COMPLETED','channel':'ANY','segment_revision_id':'','from':'','to':''},'sort':'revenue','order':'desc','limit':10}
    class Output:
        def plan(self,*unused):return 'compare_campaigns',args,0
    app.state.ai_provider=Output()
    for invalid in (0,11,True):
        args['limit']=invalid
        assert client.post('/api/v1/ai/chat',json={**base,'prompt':'비교'}).status_code==502
    args['limit']=10;args['filter']['segment_revision_id']=str(uuid4())
    assert client.post('/api/v1/ai/chat',json={**base,'prompt':'비교'}).status_code==422


def test_comparison_numeric_sort_limit_and_archive(completed,database):
    from app.models.campaigns import CampaignDelivery
    from app.services.performance import compare_campaigns
    client,query=completed
    did=UUID(query['dataset_id']); original=UUID(query['campaign_id'])
    source=client.get(f'/api/v1/campaigns/{original}',params={'dataset_id':str(did)}).json()
    payload={key:source[key] for key in ('dataset_id','segment_revision_id','name','objective','channel','benefit','brand_tone','primary_kpi','target_value')}
    payload['variants']=[{key:v[key] for key in ('variant_name','subject','body','hypothesis','allocation_bp')} for v in source['variants']]
    payload['name']='비교용 캠페인'
    created=client.post('/api/v1/campaigns',json=payload)
    assert created.status_code in (200,201),created.text
    other=UUID(created.json()['id'])
    with database.sessions.begin() as session:
        session.get(Campaign,other).status='COMPLETED'
        sent=session.scalars(select(CampaignDelivery).where(CampaignDelivery.campaign_id==original,CampaignDelivery.status=='SENT').limit(3)).all()
        for row in sent:session.add(CampaignDelivery(dataset_id=did,campaign_id=other,customer_id=row.customer_id,
            channel='EMAIL',status='SENT',sent_at=row.sent_at))
    args={'filter':{'status':'COMPLETED','channel':'ANY','segment_revision_id':'','from':'','to':''},'sort':'sent_count','order':'desc','limit':1}
    with database.sessions() as session:
        result=compare_campaigns(session,did,args,datetime.fromisoformat(query['from']),datetime.fromisoformat(query['to']))
        assert result['total_matched']==2 and len(result['campaigns'])==1
        previous={'kind':'campaign_list','campaign_ids':[str(other)]}
        args['scope']='dataset'
        all_rows=compare_campaigns(session,did,args,datetime.fromisoformat(query['from']),datetime.fromisoformat(query['to']),previous)
        assert all_rows['total_matched']==2
        args['scope']='context'
        scoped=compare_campaigns(session,did,args,datetime.fromisoformat(query['from']),datetime.fromisoformat(query['to']),previous)
        assert scoped['total_matched']==1 and scoped['campaigns'][0]['campaign_id']==str(other)
        args['scope']='dataset'
        assert result['campaigns'][0]['campaign_id']==str(original)
        args['order']='asc'
        result=compare_campaigns(session,did,args,datetime.fromisoformat(query['from']),datetime.fromisoformat(query['to']))
        assert result['campaigns'][0]['campaign_id']==str(other)
    with database.sessions.begin() as session:session.get(Campaign,other).archived_at=datetime.now(timezone.utc)
    with database.sessions() as session:
        result=compare_campaigns(session,did,args,datetime.fromisoformat(query['from']),datetime.fromisoformat(query['to']))
        assert result['total_matched']==1
