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

VALIDATION_TOOLS = [
    tool('validate_campaign', '선택한 캠페인의 대상자와 카피 정책을 검수하고 검수 기록을 남깁니다.', {}),
]

COPY_PROPERTIES = {
    'variants': {'type':'array','items':{'type':'object','properties':{
        'variant_name':{'type':'string','enum':['A','B']}, 'subject':{'type':'string'},
        'body':{'type':'string'}, 'hypothesis':{'type':'string'}},
        'required':['variant_name','subject','body','hypothesis'],'additionalProperties':False}},
    'rationale': {'type':'string'},
}
CAMPAIGN_TOOLS = [tool('create_campaign_draft','지정된 조건으로 새 캠페인 A/B 초안을 제안합니다.',COPY_PROPERTIES),
                  tool('generate_copy','선택한 캠페인의 A/B 카피 교체를 제안합니다.',COPY_PROPERTIES)]

BRIEF_TOOLS=[tool('plan_campaign','요청을 캠페인 설정으로 변환하거나 필요한 정보를 질문합니다.',{
    'question':{'type':'string','description':'정보가 부족하면 확인 질문. 충분하면 빈 문자열.'},
    'brief_json':{'type':'string','description':'CampaignBrief JSON. 질문할 때는 빈 문자열.'}})]
