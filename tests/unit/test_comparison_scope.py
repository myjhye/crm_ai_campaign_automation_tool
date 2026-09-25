import pytest
from app.services.ai_context import comparison_scope, requests_copy_creation


@pytest.mark.parametrize('prompt,suggested,expected',[
    ('이메일로 발송한 캠페인들만 비교해줘','context','dataset'),
    ('위 캠페인 중 이메일만 비교해줘','dataset','context'),
    ('그중 클릭률 높은 3개','dataset','context'),
    ('위 캠페인 말고 전체 캠페인에서 이메일만','context','dataset'),
    ('이 세그먼트의 캠페인을 비교해줘','dataset','context'),
    ('Compare these campaigns by email','dataset','context'),
    ('전체 캠페인을 비교해줘','context','dataset'),
])
def test_explicit_scope_overrides_model_guess(prompt,suggested,expected):
    assert comparison_scope(prompt,suggested)==expected


@pytest.mark.parametrize('prompt,expected',[
    ('이 고객을 대상으로 전송할 a/b 테스트 문구 추천', True),
    ('이 세그먼트로 이메일 카피를 작성해줘', True),
    ('위 캠페인을 클릭률로 비교해줘', False),
    ('A/B 테스트 성과를 비교해줘', False),
])
def test_copy_intent_is_not_performance_comparison(prompt,expected):
    assert requests_copy_creation(prompt) is expected
