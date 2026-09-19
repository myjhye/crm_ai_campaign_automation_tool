from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, AwareDatetime, model_validator
from app.schemas.common import ReportingPeriod, Pagination, Money
from pydantic import BaseModel

class AnalyticsQuery(ReportingPeriod):
    dataset_id: UUID
    data_version: int | None = Field(default=None, ge=0)

class CustomerQuery(AnalyticsQuery, Pagination):
    q: str = Field(default="", max_length=200)
    status: Literal["ACTIVE", "CHURN_RISK", "DORMANT", "WITHDRAWN"] | None = None
    sort: Literal["name", "signup_at", "total_purchase_amount", "order_count"] = "signup_at"
    direction: Literal["asc", "desc"] = "desc"
    cohort: Literal["all", "new", "active", "purchased", "repeat", "view", "cart", "purchase"] = "all"
    signup_from: AwareDatetime | None = None
    signup_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def signup_range(self):
        if self.signup_from and self.signup_to and self.signup_from >= self.signup_to:
            raise ValueError("Invalid signup range")
        return self

class CustomerRow(BaseModel):
    id: UUID
    external_id: str
    name: str | None
    email: str | None
    signup_at: datetime
    status: str
    order_count: int
    total_purchase_amount: Money
    last_purchase_at: datetime | None
    average_order_amount: Money | None
    days_since_last_purchase: int | None

class CustomerPage(BaseModel):
    dataset_id: UUID
    reference_at: datetime
    data_version: int
    items: list[CustomerRow]
    total: int
    page: int
    page_size: int

class MetricSummary(BaseModel):
    # This aggregate-only schema is the future AI tool contract. No customer fields.
    value: float | int | None
    reason: str | None = None
    unit: str
    previous_value: float | int | None = None
    difference: float | None = None
    difference_unit: str
    relative_change: float | None = None
    numerator: int | None = None
    denominator: int | None = None

class DashboardSummary(BaseModel):
    dataset_id: UUID
    reference_at: datetime
    data_version: int
    source: str
    period: dict[str, datetime]
    previous_period: dict[str, datetime]
    includes_withdrawn: bool = True
    metrics: dict[str, MetricSummary]
