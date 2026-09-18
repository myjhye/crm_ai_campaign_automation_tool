from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Index, Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityMixin


class DatasetMixin:
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))


class Customer(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "customers"
    external_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str | None] = mapped_column(String(200))
    signup_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    last_purchase_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_purchase_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, server_default="0")
    order_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    __table_args__ = (
        UniqueConstraint("dataset_id", "external_id", name="uq_customer_external"),
        UniqueConstraint("dataset_id", "id", name="uq_customer_dataset_id"),
        CheckConstraint("status IN ('ACTIVE','DORMANT','CHURN_RISK','WITHDRAWN')", name="status"),
        CheckConstraint("total_purchase_amount >= 0 AND order_count >= 0", name="purchase_totals"),
        CheckConstraint("last_purchase_at IS NULL OR last_purchase_at >= signup_at", name="purchase_time"),
        CheckConstraint("withdrawn_at IS NULL OR withdrawn_at >= signup_at", name="withdrawal_time"),
    )


class CustomerChannel(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "customer_channels"
    customer_id: Mapped[UUID]
    channel: Mapped[str] = mapped_column(String(10))
    consent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    consent_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact: Mapped[str | None] = mapped_column(String(1000))
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    hard_bounce: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    __table_args__ = (
        ForeignKeyConstraint(["dataset_id", "customer_id"], ["customers.dataset_id", "customers.id"]),
        UniqueConstraint("dataset_id", "customer_id", "channel", name="uq_customer_channel"),
        CheckConstraint("channel IN ('EMAIL','PUSH','SMS')", name="channel"),
    )


class Product(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "products"
    external_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100))
    __table_args__ = (
        UniqueConstraint("dataset_id", "external_id", name="uq_product_external"),
        UniqueConstraint("dataset_id", "id", name="uq_product_dataset_id"),
    )


class Order(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "orders"
    external_id: Mapped[str] = mapped_column(String(200))
    customer_id: Mapped[UUID]
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    __table_args__ = (
        ForeignKeyConstraint(["dataset_id", "customer_id"], ["customers.dataset_id", "customers.id"]),
        UniqueConstraint("dataset_id", "external_id", name="uq_order_external"),
        UniqueConstraint("dataset_id", "id", name="uq_order_dataset_id"),
        UniqueConstraint("dataset_id", "customer_id", "id", name="uq_order_customer_id"),
        CheckConstraint("amount >= 0", name="amount"),
        CheckConstraint("status IN ('COMPLETED','CANCELLED','REFUNDED')", name="status"),
        Index("ix_orders_customer_purchased", "customer_id", "purchased_at"),
    )


class OrderItem(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "order_items"
    order_id: Mapped[UUID]
    product_id: Mapped[UUID]
    line_id: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    __table_args__ = (
        ForeignKeyConstraint(["dataset_id", "order_id"], ["orders.dataset_id", "orders.id"]),
        ForeignKeyConstraint(["dataset_id", "product_id"], ["products.dataset_id", "products.id"]),
        UniqueConstraint("dataset_id", "order_id", "line_id", name="uq_order_line"),
        CheckConstraint("quantity > 0 AND amount >= 0", name="amount_quantity"),
    )


class CustomerEvent(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "customer_events"
    external_id: Mapped[str] = mapped_column(String(200))
    customer_id: Mapped[UUID]
    order_id: Mapped[UUID | None]
    event_type: Mapped[str] = mapped_column(String(30))
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    properties: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    __table_args__ = (
        ForeignKeyConstraint(["dataset_id", "customer_id"], ["customers.dataset_id", "customers.id"]),
        ForeignKeyConstraint(["dataset_id", "customer_id", "order_id"],
                             ["orders.dataset_id", "orders.customer_id", "orders.id"]),
        UniqueConstraint("dataset_id", "external_id", name="uq_customer_event_external"),
        CheckConstraint("event_type IN ('VIEW','CART','PURCHASE','EMAIL_OPEN','CLICK','LANDING_VIEW','UNSUBSCRIBE')", name="event_type"),
        CheckConstraint("event_type != 'PURCHASE' OR order_id IS NOT NULL", name="purchase_order"),
        Index("ix_customer_events_customer_time", "customer_id", "event_at"),
    )
