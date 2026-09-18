from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityMixin
from app.models.customers import DatasetMixin


class Job(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None]
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    result: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(100))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("dataset_id", "kind", "idempotency_key", name="uq_job_idempotency"),
        UniqueConstraint("dataset_id", "id", name="uq_job_dataset_id"),
        CheckConstraint("status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')", name="status"),
        CheckConstraint("attempt >= 0 AND max_attempts > 0 AND attempt <= max_attempts", name="attempts"),
        CheckConstraint("progress BETWEEN 0 AND 100", name="progress"),
        CheckConstraint("(status = 'RUNNING' AND lease_token IS NOT NULL AND lease_until IS NOT NULL AND heartbeat_at IS NOT NULL) OR (status != 'RUNNING' AND lease_token IS NULL AND lease_until IS NULL)", name="lease"),
        Index("ix_jobs_available", "status", "available_at"),
        Index("ix_jobs_lease", "status", "lease_until"),
    )


class ImportBatch(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "import_batches"
    kind: Mapped[str] = mapped_column(String(50))
    file_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="PREVIEW", server_default="PREVIEW")
    job_id: Mapped[UUID | None]
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    __table_args__ = (
        ForeignKeyConstraint(["dataset_id", "job_id"], ["jobs.dataset_id", "jobs.id"]),
        CheckConstraint("status IN ('PREVIEW','INVALID','QUEUED','COMPLETED','FAILED')", name="status"),
    )


class DatasetVersion(IdentityMixin, DatasetMixin, Base):
    __tablename__ = "dataset_versions"
    version: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    __table_args__ = (
        UniqueConstraint("dataset_id", "version", name="uq_dataset_version"),
        CheckConstraint("version > 0", name="version"),
    )
