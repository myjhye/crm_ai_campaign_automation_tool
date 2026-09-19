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
