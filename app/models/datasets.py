from uuid import UUID
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, Integer, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityMixin


class Dataset(IdentityMixin, Base):
    __tablename__ = "datasets"
    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20), default="DEMO", server_default="DEMO")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("source IN ('DEMO','UPLOADED','SIMULATED')", name="source"),
        CheckConstraint("version > 0", name="version"),
    )


class AuditLog(IdentityMixin, Base):
    __tablename__ = "audit_logs"
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    actor_type: Mapped[str] = mapped_column(String(20))
    resource_id: Mapped[UUID | None]
    action: Mapped[str] = mapped_column(String(80))
    request_id: Mapped[UUID | None]
    event_key: Mapped[str | None] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    previous_version: Mapped[int | None] = mapped_column(Integer)
    new_version: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint("actor_type IN ('VISITOR','AI','SYSTEM')", name="actor_type"),
        UniqueConstraint("dataset_id", "event_key", name="uq_audit_event_key"),
        CheckConstraint("previous_version IS NULL OR previous_version > 0", name="previous_version"),
        CheckConstraint("new_version IS NULL OR new_version > 0", name="new_version"),
        Index("ix_audit_dataset_created", "dataset_id", "created_at", "id"),
    )
