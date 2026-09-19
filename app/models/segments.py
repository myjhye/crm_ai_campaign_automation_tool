from datetime import datetime
from uuid import UUID
from sqlalchemy import String, Integer, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin

class Segment(IdentityMixin, Base):
    __tablename__ = 'segments'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('dataset_id', 'id', name='uq_segment_dataset_id'), CheckConstraint('version > 0', name='version'))

class SegmentRevision(IdentityMixin, Base):
    __tablename__ = 'segment_revisions'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    segment_id: Mapped[UUID]
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    condition_json: Mapped[dict] = mapped_column(JSONB)
    reference_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_version: Mapped[int] = mapped_column(Integer)
    condition_hash: Mapped[str] = mapped_column(String(64))
    created_source: Mapped[str] = mapped_column(String(20), default='VISITOR', server_default='VISITOR')
    __table_args__ = (ForeignKeyConstraint(['dataset_id', 'segment_id'], ['segments.dataset_id', 'segments.id']), UniqueConstraint('segment_id', 'version', name='uq_segment_revision'), UniqueConstraint('dataset_id', 'id', name='uq_segment_revision_dataset'), CheckConstraint('version > 0 AND data_version >= 0', name='versions'), CheckConstraint("created_source IN ('VISITOR','AI','SYSTEM')", name='source'))
