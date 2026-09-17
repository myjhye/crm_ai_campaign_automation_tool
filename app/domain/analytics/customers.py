"""Customer state as of a supplied reference time; no database access."""

from datetime import datetime
from enum import Enum

from app.core.time import as_utc


class CustomerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    CHURN_RISK = "CHURN_RISK"
    DORMANT = "DORMANT"
    WITHDRAWN = "WITHDRAWN"


def days_since_last_purchase(
    last_purchase_at: datetime | None, reference_at: datetime
) -> int | None:
    reference_at = as_utc(reference_at)
    if last_purchase_at is None:
        return None
    purchase = as_utc(last_purchase_at)
    if purchase > reference_at:
        raise ValueError("Purchase must be selected as of reference time")
    return (reference_at - purchase).days


def customer_status(
    *, signup_at: datetime, reference_at: datetime,
    last_purchase_at: datetime | None = None, withdrawn_at: datetime | None = None,
) -> CustomerStatus:
    signup = as_utc(signup_at)
    reference = as_utc(reference_at)
    if signup > reference:
        raise ValueError("Customer did not exist at reference time")
    if last_purchase_at is not None and as_utc(last_purchase_at) < signup:
        raise ValueError("Purchase precedes signup")
    elapsed = days_since_last_purchase(last_purchase_at, reference)
    if withdrawn_at is not None:
        withdrawn = as_utc(withdrawn_at)
        if withdrawn < signup:
            raise ValueError("Withdrawal precedes signup")
        if withdrawn <= reference:
            return CustomerStatus.WITHDRAWN
    days = elapsed if elapsed is not None else (reference - signup).days
    if days >= 60:
        return CustomerStatus.DORMANT
    if days >= 30:
        return CustomerStatus.CHURN_RISK
    return CustomerStatus.ACTIVE
