import json
import re
import time
import httpx
from app.ai.tools import TOOLS
from app.domain.segments.fields import FIELDS
from app.core.errors import AppError


def safe_prompt(prompt):
    # Do not send contact details, keys, or customer-specific requests to the model.
    if re.search(r'[\w.+-]+@[\w.-]+|(?:\+?82|0\d{1,2})[- .]?\d{3,4}[- .]?\d{4}|sk-[\w-]+|\d{6}-?[1-4]\d{6}', prompt):
        raise AppError('AI_PRIVATE_INPUT', '연락처나 비밀값을 제외하고 집계 조건만 입력해주세요.', 422)
    return prompt


class MockProvider:
    """Deliberately limited fixtures, never pretend to interpret arbitrary language."""
    def plan(self, prompt, context):
        if prompt.strip() == '활성 고객 수를 알려줘':
            return 'get_metric', {'metric': 'active_customers'}, 0
        if prompt.strip() == '60일 미구매, 누적 30만원 이상, 이메일 동의 고객을 저장할 초안으로 만들어줘':
            condition = {'operator': 'AND', 'conditions': [
                {'field': 'days_since_last_purchase', 'comparison': 'GTE', 'value': 60},
                {'field': 'total_purchase_amount', 'comparison': 'GTE', 'value': '300000'},
                {'field': 'email_consent', 'comparison': 'EQ', 'value': True}]}
            return 'create_segment_draft', {'name': '휴면 VIP', 'condition_json': json.dumps(condition)}, 0
        return 'clarify', {'question': '모의 모드는 아래 예시 두 가지를 지원합니다. 자유로운 요청은 실제 AI 연결 후 사용할 수 있습니다.'}, 0


class OpenAIProvider:
    def __init__(self, settings):
        self.settings = settings

    def plan(self, prompt, context):
        s = self.settings
        if not s.openai_api_key:
            raise AppError('AI_NOT_CONFIGURED', '서버의 AI 연결 설정이 필요합니다.', 503)
        instructions = ('CRM 집계 도구 하나만 선택하세요. 고객 개인 정보나 SQL은 취급하지 않습니다. '
            'VIP처럼 기준이 모호하면 clarify로 금액/기간/채널을 질문하세요. 요청이 화면의 기간과 다르면 기간 필터 변경을 요청하세요. '
            '저장 요청에는 create_segment_draft, 조회에는 preview_segment를 사용하세요. 발송/승인/캠페인은 미지원입니다. '
            'DSL은 {operator:AND|OR,conditions:[...]} 또는 {field,comparison,value}입니다. '
            '금액 value는 문자열, boolean은 JSON boolean, IS_NULL에는 value를 생략하세요. '
            '필드와 연산자: ' + json.dumps(FIELDS, ensure_ascii=False) + '\n화면 기준: ' + json.dumps(context))
        body = {'model': s.ai_model, 'store': False, 'instructions': instructions,
                'input': prompt, 'tools': TOOLS, 'tool_choice': 'required', 'parallel_tool_calls': False,
                'max_output_tokens': s.ai_max_output_tokens}
        deadline = time.monotonic() + s.ai_timeout_seconds
        for attempt in range(2):
            try:
                with httpx.Client(timeout=max(.1, deadline - time.monotonic())) as client:
                    with client.stream('POST', 'https://api.openai.com/v1/responses', json=body,
                            headers={'Authorization': 'Bearer ' + s.openai_api_key.get_secret_value()}) as response:
                        if response.status_code == 429 or response.status_code >= 500:
                            if attempt == 0 and time.monotonic() < deadline: continue
                            raise AppError('AI_UNAVAILABLE', 'AI가 혼잡합니다. 잠시 후 다시 시도해주세요.', 503)
                        if response.status_code != 200:
                            raise AppError('AI_PROVIDER_ERROR', 'AI 연결 설정 또는 요청을 확인해주세요.', 502)
                        chunks = bytearray()
                        for chunk in response.iter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > 100_000 or time.monotonic() > deadline:
                                raise AppError('AI_LIMIT', 'AI 응답 제한을 초과했습니다.', 502)
                        data = json.loads(chunks)
                if data.get('status') != 'completed':
                    raise AppError('AI_INCOMPLETE', 'AI 응답이 완료되지 않았습니다. 다시 시도해주세요.', 502)
                calls = [item for item in data.get('output', []) if item.get('type') == 'function_call']
                if len(calls) != 1:
                    raise AppError('AI_INVALID_OUTPUT', 'AI가 실행 가능한 응답을 반환하지 않았습니다.', 502)
                call = calls[0]
                return call['name'], json.loads(call['arguments']), data.get('usage', {}).get('total_tokens', 0)
            except (httpx.HTTPError, TimeoutError):
                raise AppError('AI_TIMEOUT', 'AI 연결 시간이 초과되었습니다. 다시 시도해주세요.', 504) from None
            except (ValueError, KeyError, TypeError):
                raise AppError('AI_INVALID_OUTPUT', 'AI 응답 형식이 올바르지 않습니다.', 502) from None
