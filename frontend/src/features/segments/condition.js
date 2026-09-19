export const vipTemplate = () => ({operator: 'AND', conditions: [
  {field: 'days_since_last_purchase', comparison: 'GTE', value: 60},
  {field: 'total_purchase_amount', comparison: 'GTE', value: '300000'},
  {field: 'email_consent', comparison: 'EQ', value: true},
]});
const consent = {field: 'email_consent', comparison: 'EQ', value: true};
const notWithdrawn = {field: 'status', comparison: 'NEQ', value: 'WITHDRAWN'};
export const segmentTemplates = [
  {id: 'dormant_vip', label: '휴면 VIP', description: '60일 이상 미구매 · 누적 구매액 30만 원 이상 · 이메일 동의', condition: vipTemplate()},
  {id: 'first_purchase', label: '첫 구매 유도', description: '완료 주문 0건 · 탈퇴 제외 · 이메일 동의', condition: {operator: 'AND', conditions: [
    {field: 'order_count', comparison: 'EQ', value: 0}, notWithdrawn, consent,
  ]}},
  {id: 'second_purchase', label: '재구매 유도', description: '완료 주문 1건 · 마지막 구매 후 7~29일 · 탈퇴 제외 · 이메일 동의', condition: {operator: 'AND', conditions: [
    {field: 'order_count', comparison: 'EQ', value: 1}, {field: 'days_since_last_purchase', comparison: 'BETWEEN', value: [7, 29]}, notWithdrawn, consent,
  ]}},
  {id: 'churn_risk', label: '이탈 위험', description: '이탈 위험 상태 · 이메일 동의', condition: {operator: 'AND', conditions: [
    {field: 'status', comparison: 'EQ', value: 'CHURN_RISK'}, consent,
  ]}},
  {id: 'loyal', label: '충성 고객', description: '완료 주문 3건 이상 · 최근 30일 내 구매 · 누적 구매액 30만 원 이상 · 탈퇴 제외 · 이메일 동의', condition: {operator: 'AND', conditions: [
    {field: 'order_count', comparison: 'GTE', value: 3}, {field: 'days_since_last_purchase', comparison: 'LT', value: 30}, {field: 'total_purchase_amount', comparison: 'GTE', value: '300000'}, notWithdrawn, consent,
  ]}},
  {id: 'email_engaged', label: '이메일 반응 고객', description: '최근 30일 이메일 오픈 2회 이상 · 탈퇴 제외 · 이메일 동의', condition: {operator: 'AND', conditions: [
    {field: 'email_opens_30d', comparison: 'GTE', value: 2}, notWithdrawn, consent,
  ]}},
];
export function templateCondition(id) {
  const template = segmentTemplates.find(item => item.id === id);
  if (!template) throw new Error('알 수 없는 추천 유형입니다.');
  return structuredClone(template.condition);
}
export function parseValue(text, type, comparison) {
  if (['IS_NULL', 'IS_NOT_NULL'].includes(comparison)) return undefined;
  const scalar = value => {
    if (type === 'integer') {
      if (!/^\d+$/.test(value.trim())) throw new Error('0 이상의 정수를 입력해주세요.');
      const number = Number(value); if (!Number.isSafeInteger(number)) throw new Error('숫자가 너무 큽니다.'); return number;
    }
    if (type === 'boolean') return value === 'true';
    return value.trim();
  };
  if (['IN', 'NOT_IN', 'BETWEEN'].includes(comparison)) return text.split(',').map(scalar);
  return scalar(text);
}
