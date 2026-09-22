import json
import httpx
import pytest
from app.ai.provider import OpenAIProvider, safe_prompt, MockProvider
from app.core.config import Settings
from app.core.errors import AppError


def test_live_wire_contract_and_retry(monkeypatch):
    original = httpx.Client
    requests = []
    def handler(request):
        body = json.loads(request.content); requests.append(body)
        if len(requests) == 1: return httpx.Response(429)
        return httpx.Response(200,json={'status':'completed','output':[{'type':'function_call','name':'get_metric','arguments':'{"metric":"active_customers"}'}],'usage':{'total_tokens':12}})
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    provider = OpenAIProvider(Settings(_env_file=None, openai_api_key='test'))
    assert provider.plan('활성 고객', {}) == ('get_metric', {'metric':'active_customers'}, 12)
    assert len(requests) == 2
    assert requests[0]['store'] is False and requests[0]['parallel_tool_calls'] is False
    assert all(tool['strict'] for tool in requests[0]['tools'])
    comparison=next(t for t in requests[0]['tools'] if t['name']=='compare_campaigns')
    nested=comparison['parameters']['properties']['filter']
    assert nested['additionalProperties'] is False
    assert set(nested['required'])==set(nested['properties'])
    assert not any(t['name']=='prepare_campaign' for t in requests[0]['tools'])


def test_timeout_and_no_key(monkeypatch):
    with pytest.raises(AppError): OpenAIProvider(Settings(_env_file=None)).plan('test', {})
    original = httpx.Client
    def handler(request): raise httpx.ReadTimeout('secret provider detail')
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(AppError) as error: OpenAIProvider(Settings(_env_file=None, openai_api_key='test')).plan('test', {})
    assert 'secret' not in str(error.value)


def test_privacy_and_ambiguous_mock():
    for prompt in ['a@example.com', '010-1234-5678', 'sk-secret']:
        with pytest.raises(AppError): safe_prompt(prompt)
    assert MockProvider().plan('VIP 찾아줘', {})[0] == 'clarify'


def test_performance_wire_contract_is_evidence_only(monkeypatch):
    from app.ai.performance import analysis_tool
    original=httpx.Client;captured=[]
    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,json={'status':'completed','output':[{'type':'function_call','name':'analyze_campaign',
            'arguments':json.dumps({'facts':[{'metric_id':'A.conversion_rate'}],'hypotheses':[],'recommended_actions':['RETEST']})}]})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    refs={'A.conversion_rate':{'value':'3.27','label':'A안 전환율','unit':'%'}}
    context={'performance':{'metric_refs':refs},'analysis_tool':analysis_tool(refs)}
    result=OpenAIProvider(Settings(_env_file=None,openai_api_key='test')).plan('성과 분석',context)
    assert result[0]=='analyze_campaign'
    body=captured[0];assert body['store'] is False
    assert len(body['tools'])==1 and body['tools'][0]['strict'] is True
    assert body['tools'][0]['parameters']['properties']['facts']['items']['properties']['metric_id']['enum']==['A.conversion_rate']
    assert set(body['tools'][0]['parameters']['properties']['facts']['items']['properties'])=={'metric_id'}
    # The strict wire contract must enforce the same list bounds as the server.
    from app.ai.performance import AnalysisSelection
    properties=body['tools'][0]['parameters']['properties']
    validated=AnalysisSelection.model_json_schema()['properties']
    for field in ('facts','hypotheses','recommended_actions'):
        for bound in ('minItems','maxItems'):
            assert properties[field].get(bound)==validated[field].get(bound)

def test_campaign_validation_uses_the_only_bounded_tool(monkeypatch):
    original=httpx.Client; captured=[]
    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200,json={'status':'completed','output':[{'type':'function_call','name':'validate_campaign','arguments':'{}'}]})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    provider=OpenAIProvider(Settings(_env_file=None,openai_api_key='test'))
    context={'validation_campaign':{'id':'campaign','name':'검수 캠페인','channel':'EMAIL','status':'DRAFT','version':1}}
    assert provider.plan('검수해줘',context)[0:2]==('validate_campaign',{})
    assert [tool['name'] for tool in captured[0]['tools']]==['validate_campaign']
    assert captured[0]['tools'][0]['parameters']['properties']=={}
