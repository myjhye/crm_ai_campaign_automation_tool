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

COMPARE_TOOLS = [tool('compare_campaigns', '선택한 발송 기간의 완료 캠페인을 비교합니다. 카피와 고객 행은 조회하지 않습니다.', {
    'scope': {'type':'string','enum':['dataset','context'],'description':'일반 채널·기간 비교는 dataset. 사용자가 위 캠페인/그중/이 세그먼트처럼 이전 대상을 명시한 경우만 context.'},
    'filter': {'type': 'object', 'properties': {
        'status': {'type': 'string', 'enum': ['COMPLETED']},
        'channel': {'type': 'string', 'enum': ['EMAIL','PUSH','SMS','ANY']},
        'segment_revision_id': {'type': 'string', 'description': '제공된 revision UUID 또는 전체 조회는 빈 문자열'},
        'from': {'type': 'string', 'description': '시간대 포함 ISO8601 또는 화면 기간은 빈 문자열'},
        'to': {'type': 'string', 'description': '종료 미포함 ISO8601 또는 화면 기간은 빈 문자열'}},
        'required': ['status','channel','segment_revision_id','from','to'], 'additionalProperties': False},
    'sort': {'type':'string','enum':['conversion_rate','click_rate','revenue','sent_count']},
    'order': {'type':'string','enum':['desc','asc']}, 'limit': {'type':'integer','minimum':1,'maximum':10}})]

# The segment is a server-resolved reference, never an ID supplied by the model.
WORKFLOW_TOOLS = [tool('prepare_campaign', '현재 저장된 세그먼트로 확인 저장용 캠페인 제안을 준비합니다. 채널·혜택이 없으면 빈 문자열로 질문합니다.', {
    'channel': {'type':'string','enum':['EMAIL','PUSH','SMS','']},
    'benefit': {'type':'string','description':'이번 사용자 입력의 혜택 원문. 없으면 빈 문자열'},
    'objective': {'type':'string','description':'캠페인 목표. 없으면 재구매 유도'},
    'brand_tone': {'type':'string','description':'공통 말투. 없으면 다정하고 편안하게'}})]

COPY_PROPERTIES = {
    'variants': {'type':'array','items':{'type':'object','properties':{
        'variant_name':{'type':'string','enum':['A','B']}, 'subject':{'type':'string'},
        'body':{'type':'string'}, 'hypothesis':{'type':'string'}},
        'required':['variant_name','subject','body','hypothesis'],'additionalProperties':False}},
    'rationale': {'type':'string'},
}
ADVICE_TOOLS = [tool('recommend_copy', '저장 없이 고객에게 보낼 A/B 문구 두 안을 추천합니다. 미저장 고객 조건도 사용 가능합니다. 실제 성과 수치를 만들지 않습니다.', {
    **COPY_PROPERTIES,
    'channel': {'type':'string','enum':['EMAIL','PUSH','SMS','UNSPECIFIED']},
})]
CAMPAIGN_TOOLS = [tool('create_campaign_draft','지정된 조건으로 새 캠페인 A/B 초안을 제안합니다.',COPY_PROPERTIES),
                  tool('generate_copy','선택한 캠페인의 A/B 카피 교체를 제안합니다.',COPY_PROPERTIES)]

BRIEF_TOOLS=[tool('plan_campaign','요청을 캠페인 설정으로 변환하거나 필요한 정보를 질문합니다.',{
    'question':{'type':'string','description':'정보가 부족하면 확인 질문. 충분하면 빈 문자열.'},
    'brief_json':{'type':'string','description':'CampaignBrief JSON. 질문할 때는 빈 문자열.'}})]
