from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from app.core.time import FixedClock, as_utc, inclusive_dates_to_utc
from app.domain.analytics.customers import customer_status, days_since_last_purchase
from app.domain.analytics.metrics import percentage
from app.schemas.common import Money, Page, Pagination, ReportingPeriod

REFERENCE = datetime(2026, 9, 14, tzinfo=timezone.utc)


@pytest.mark.parametrize("days,expected", [(29, "ACTIVE"), (30, "CHURN_RISK"),
                                          (59, "CHURN_RISK"), (60, "DORMANT")])
@pytest.mark.parametrize("purchased", [False, True])
def test_customer_boundaries(days, expected, purchased):
    anchor = REFERENCE - timedelta(days=days)
    assert customer_status(
        signup_at=anchor - timedelta(days=100) if purchased else anchor,
        last_purchase_at=anchor if purchased else None,
        reference_at=REFERENCE,
    ) == expected


def test_withdrawal_and_missing_purchase():
    assert days_since_last_purchase(None, REFERENCE) is None
    assert customer_status(signup_at=REFERENCE - timedelta(days=90),
                           withdrawn_at=REFERENCE, reference_at=REFERENCE) == "WITHDRAWN"
    assert customer_status(signup_at=REFERENCE, withdrawn_at=REFERENCE + timedelta(days=1),
                           reference_at=REFERENCE) == "ACTIVE"
    with pytest.raises(ValueError):
        days_since_last_purchase(REFERENCE + timedelta(seconds=1), REFERENCE)
    with pytest.raises(ValueError):
        customer_status(signup_at=REFERENCE + timedelta(days=1), reference_at=REFERENCE)


def test_elapsed_day_and_timezone_boundaries():
    assert days_since_last_purchase(REFERENCE - timedelta(days=30, microseconds=-1), REFERENCE) == 29
    start, end = inclusive_dates_to_utc(date(2026, 9, 14), date(2026, 9, 14))
    assert start == datetime(2026, 9, 13, 15, tzinfo=timezone.utc)
    assert end - start == timedelta(days=1)
    period = ReportingPeriod(start=start, end=end)
    assert period.contains(start)
    assert not period.contains(end)
    assert period.previous().end == start
    assert period.previous().end - period.previous().start == end - start
    assert FixedClock(start).now() == start
    with pytest.raises(ValueError):
        as_utc(datetime(2026, 9, 14))
    with pytest.raises(ValueError):
        inclusive_dates_to_utc(date(2026, 9, 15), date(2026, 9, 14))


@pytest.mark.parametrize("payload", [
    {"from": "2026-09-14", "to": "2026-09-15"},
    {"from": "2026-09-15T00:00:00Z", "to": "2026-09-14T00:00:00Z"},
    {"from": "2026-09-14T00:00:00Z", "to": "2026-09-14T00:00:00Z"},
])
def test_invalid_period(payload):
    with pytest.raises(ValidationError):
        ReportingPeriod.model_validate(payload)


def test_pagination_money_and_zero_denominator():
    assert Pagination().page_size == 20
    assert Pagination(page=3, page_size=10).offset == 20
    assert Page[int](items=[], total=0, page=1, page_size=20).items == []
    for payload in ({"page": 0}, {"page_size": 101}, {"page_size": 0}):
        with pytest.raises(ValidationError):
            Pagination(**payload)

    class Price(BaseModel):
        amount: Money

    assert Price(amount="300000.10").model_dump(mode="json") == {"amount": "300000.10"}
    for value in ("-1", "NaN", "Infinity"):
        with pytest.raises(ValidationError):
            Price(amount=value)
    assert percentage(0, 0).model_dump() == {"value": None, "reason": "NO_DENOMINATOR"}
    assert percentage(0, 10).value == 0
    assert percentage(1, 4).value == Decimal("25")
    with pytest.raises(ValueError):
        percentage(2, 1)
