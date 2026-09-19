"""The model selects a single bounded operation; dataset scope is server-owned."""
METRICS = ['total_customers', 'active_customers', 'new_customers', 'dormant_customers', 'purchase_conversion_rate', 'repeat_purchase_rate']


def tool(name, description, properties):
    return {'type': 'function', 'name': name, 'description': description, 'strict': True,
            'parameters': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}}


TOOLS = [
    tool('get_metric', '선택한 기간의 CRM 지표를 조회합니다.', {'metric': {'type': 'string', 'enum': METRICS}}),
    tool('preview_segment', '조건에 맞는 고객을 미리 봅니다. 저장하지 않습니다.', {'condition_json': {'type': 'string', 'description': '허용된 DSL JSON 문자열'}}),
    tool('create_segment_draft', '조건을 미리 보고 방문자가 확인할 저장 제안을 만듭니다. 아직 저장하지 않습니다.',
         {'name': {'type': 'string'}, 'condition_json': {'type': 'string'}}),
    tool('clarify', '모호한 조건, 다른 기간 요청 또는 미지원 업무의 확인 질문을 합니다.', {'question': {'type': 'string'}}),
]
