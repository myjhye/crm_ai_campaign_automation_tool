"""Typed CSV row contracts. Raw values never appear in public error details."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, field_validator, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=200)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]
Kind = Literal["customers", "products", "orders", "order_items", "events"]
Mode = Literal["insert", "upsert"]

class Row(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def utc(cls, value):
        return value.astimezone(timezone.utc) if isinstance(value, datetime) else value

class CustomerRow(Row):
    external_id: Identifier
    signup_at: AwareDatetime
    status: Literal["ACTIVE", "CHURN_RISK", "DORMANT", "WITHDRAWN"]
    email_consent: bool
    name: Annotated[str, Field(max_length=200)] | None = None
    withdrawn_at: AwareDatetime | None = None
    email: Annotated[str, Field(max_length=254)] | None = None
    email_valid: bool = False
    hard_bounce: bool = False
    consent_changed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "WITHDRAWN") != (self.withdrawn_at is not None):
            raise ValueError("Withdrawal timestamp required only for withdrawn customers")
        if self.withdrawn_at and self.withdrawn_at < self.signup_at:
            raise ValueError("Withdrawal before signup")
        if self.email and (self.email.count("@") != 1 or any(c.isspace() for c in self.email)):
            raise ValueError("Invalid email")
        if self.email_valid and not self.email:
            raise ValueError("Valid contact requires email")
        return self

class ProductRow(Row):
    external_id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=200)]
    category: Annotated[str, Field(min_length=1, max_length=100)]

class OrderRow(Row):
    external_id: Identifier
    customer_external_id: Identifier
    purchased_at: AwareDatetime
    status: Literal["COMPLETED", "CANCELLED", "REFUNDED"]
    amount: Amount

class ItemRow(Row):
    order_external_id: Identifier
    line_id: Annotated[str, Field(min_length=1, max_length=100)]
    product_external_id: Identifier
    quantity: Annotated[int, Field(gt=0, le=2147483647)]
    amount: Amount

class EventProperties(Row):
    device_type: Literal["mobile", "desktop", "tablet"] | None = None
    page: Annotated[str, Field(max_length=200, pattern=r"^/[a-zA-Z0-9/_-]*$")] | None = None
    category: Annotated[str, Field(max_length=100)] | None = None

class EventRow(Row):
    external_id: Identifier
    customer_external_id: Identifier
    event_type: Literal["VIEW", "CART", "PURCHASE", "EMAIL_OPEN", "CLICK", "LANDING_VIEW", "UNSUBSCRIBE"]
    event_at: AwareDatetime
    order_external_id: Identifier | None = None
    properties: EventProperties = Field(default_factory=EventProperties)

    @model_validator(mode="after")
    def purchase_order(self):
        if self.event_type == "PURCHASE" and self.order_external_id is None:
            raise ValueError("Purchase requires order")
        return self

SCHEMAS = {"customers": CustomerRow, "products": ProductRow, "orders": OrderRow,
           "order_items": ItemRow, "events": EventRow}
