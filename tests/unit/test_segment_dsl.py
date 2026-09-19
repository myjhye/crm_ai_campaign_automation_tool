import pytest
from app.schemas.segments import PreviewRequest
from app.domain.segments.dsl import Condition
from app.services.segments import digest, ai_profile
from app.domain.segments.human_readable import describe


def leaf(field='order_count', comparison='GTE', value=1):
    return dict(field=field, comparison=comparison, value=value)

@pytest.mark.parametrize('node', [leaf(value=True), leaf(value='1'), leaf(field='email'), leaf(comparison='SQL'), leaf(field='total_purchase_amount', value=300000), leaf(field='total_purchase_amount',value='NaN'), leaf(comparison='BETWEEN',value=[2,1]), leaf(comparison='IN', value=list(range(101))), leaf(comparison='IS_NULL',value=None), {'operator':'AND','conditions':[]}, leaf(field='email_consent',value=1)])
def test_rejects_invalid_dsl(node):
    with pytest.raises(ValueError): Condition.model_validate(node)


def test_limits_alias_and_canonical_hash():
    a = Condition.model_validate(leaf('marketing_consent','EQ',True))
    b = Condition.model_validate(leaf('email_consent','EQ',True))
    assert digest(a) == digest(b)
    assert '이메일' in describe(a)
    node = leaf()
    for _ in range(4): node = {'operator':'AND','conditions':[node]}
    with pytest.raises(ValueError): PreviewRequest(dataset_id='11111111-1111-4111-8111-111111111111', reference_at='2026-09-19T00:00:00Z', condition=node)
    assert ai_profile({'count': 1}) == {'status':'insufficient_population'}
def test_human_readable_units_and_consent():
    group = Condition.model_validate({'operator': 'AND', 'conditions': [leaf('days_since_last_purchase','GTE',60), leaf('email_consent','EQ',True)]})
    assert describe(group) == '마지막 구매 후 60일 이상 · 이메일 수신 동의'
    nested = Condition.model_validate({'operator': 'AND', 'conditions': [leaf(), {'operator': 'OR', 'conditions': [leaf(value=2), leaf(value=3)]}]})
    assert describe(nested) == '완료 주문 수 1건 이상 · (완료 주문 수 2건 이상 또는 완료 주문 수 3건 이상)'
    assert describe(Condition.model_validate(leaf('email_consent','EQ',True))) == '이메일 수신 동의'
    assert describe(Condition.model_validate(leaf('email_consent','NEQ',True))) == '이메일 수신 미동의'
    assert describe(Condition.model_validate(leaf('total_purchase_amount','GTE','300000.00'))) == '누적 구매액 300,000원 이상'
    assert describe(Condition.model_validate(leaf('days_since_last_purchase','GTE',60))) == '마지막 구매 후 60일 이상'
