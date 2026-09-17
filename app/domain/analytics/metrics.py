from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class MetricValue(BaseModel):
    value: Decimal | None
    reason: Literal["NO_DENOMINATOR"] | None = None


def percentage(numerator: int, denominator: int) -> MetricValue:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise ValueError("Counts must satisfy 0 <= numerator <= denominator")
    if denominator == 0:
        return MetricValue(value=None, reason="NO_DENOMINATOR")
    return MetricValue(value=Decimal(numerator) / Decimal(denominator) * 100)
