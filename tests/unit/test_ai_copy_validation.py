import pytest
from app.ai.campaigns import number_tokens, normalized_benefit
from app.ai.campaigns import unsupported_numbers,expiry_labels


def test_expiry_matches_complete_korean_date_after_timezone_conversion():
    base={'benefit':'10% 할인','coupon_expires_at':'2026-09-30T15:00:00Z'}
    assert expiry_labels(base['coupon_expires_at'])[0]=='2026년 10월 1일 00:00'
    assert not unsupported_numbers('10% 할인 · 2026년 10월 1일 00:00까지',base)
    assert unsupported_numbers('10% 할인 · 2026년 10월 2일까지',base)
    assert unsupported_numbers('30일 동안 10% 할인',base)
    assert unsupported_numbers('2026원 할인',base)
    assert unsupported_numbers('10월 1일 마감',{'benefit':'10% 할인','coupon_expires_at':None})


def test_numeric_formatting_preserves_value_and_unit():
    assert number_tokens('1,000 원 할인') == number_tokens('1000원 할인')
    assert number_tokens('10 % 할인') == number_tokens('10% 할인')
    assert number_tokens('10명') != number_tokens('10%')
    assert not number_tokens('90%').issubset(number_tokens('10%'))
    assert number_tokens('1000원') != number_tokens('1000')


def test_benefit_normalizes_only_formatting():
    assert normalized_benefit('1,000원 할인 쿠폰') == normalized_benefit('1000 원 할인\n쿠폰')
    assert normalized_benefit('10% 할인') != normalized_benefit('90% 할인')
    assert normalized_benefit('10% coupon') != normalized_benefit('10% 할인')
