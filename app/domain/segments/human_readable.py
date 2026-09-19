from decimal import Decimal
from app.domain.segments.fields import FIELDS
LABELS = {'EQ': '일치', 'NEQ': '제외', 'GT': '초과', 'GTE': '이상', 'LT': '미만', 'LTE': '이하'}
STATUS = {'ACTIVE': '활성', 'CHURN_RISK': '이탈 위험', 'DORMANT': '휴면', 'WITHDRAWN': '탈퇴'}


def describe(node, nested=False):
    if node.operator:
        text = (' · ' if node.operator == 'AND' else ' 또는 ').join(describe(child, nested=True) for child in node.conditions)
        return f'({text})' if nested else text
    field, op = node.field, node.comparison
    label = {'days_since_last_purchase': '마지막 구매 후', 'total_purchase_amount': '누적 구매액'}.get(field, FIELDS[field]['label'])
    if op in ('IS_NULL', 'IS_NOT_NULL'):
        if field == 'days_since_last_purchase': return '구매 이력 없음' if op == 'IS_NULL' else '구매 이력 있음'
        return f"{label} {'정보 없음' if op == 'IS_NULL' else '정보 있음'}"
    if field == 'email_consent':
        consent = node.value if op == 'EQ' else not node.value
        return '이메일 수신 동의' if consent else '이메일 수신 미동의'
    def value_text(value):
        if field == 'total_purchase_amount':
            formatted = format(Decimal(value), ',f')
            if '.' in formatted: formatted = formatted.rstrip('0').rstrip('.')
            return formatted + '원'
        if field == 'status': return STATUS[value]
        if isinstance(value, int):
            unit = '일' if field == 'days_since_last_purchase' else '회' if field == 'email_opens_30d' else '건'
            return f'{value:,}{unit}'
        return str(value)
    if op == 'BETWEEN': return f'{label} {value_text(node.value[0])}~{value_text(node.value[1])} (양끝 포함)'
    if op in ('IN', 'NOT_IN'):
        values = ', '.join(value_text(value) for value in node.value)
        return f"{label}: [{values}] {'중 하나' if op == 'IN' else '제외'}"
    return f'{label} {value_text(node.value)} {LABELS[op]}'
