from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import String, Text, Integer, Numeric, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class Campaign(IdentityMixin, Base):
    __tablename__ = 'campaigns'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    segment_revision_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(String(500))
    channel: Mapped[str] = mapped_column(String(10))
    benefit: Mapped[str] = mapped_column(String(1000))
    brand_tone: Mapped[str] = mapped_column(String(200))
    primary_kpi: Mapped[str] = mapped_column(String(40))
    target_value: Mapped[Decimal] = mapped_column(Numeric(18,2))
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coupon_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='DRAFT', server_default='DRAFT')
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    policy_version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    __table_args__ = (
        UniqueConstraint('dataset_id','id',name='uq_campaign_dataset'),
        ForeignKeyConstraint(['dataset_id','segment_revision_id'],['segment_revisions.dataset_id','segment_revisions.id']),
        CheckConstraint("channel IN ('EMAIL','PUSH','SMS')",name='channel'),
        CheckConstraint("status IN ('DRAFT','REVIEW','APPROVED','RUNNING','COMPLETED','CANCELLED')",name='status'),
        CheckConstraint('version > 0 AND policy_version > 0 AND target_value >= 0',name='values'))


class CampaignVariant(IdentityMixin, Base):
    __tablename__ = 'campaign_variants'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    campaign_id: Mapped[UUID]
    variant_name: Mapped[str] = mapped_column(String(1))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    hypothesis: Mapped[str] = mapped_column(String(1000))
    allocation_bp: Mapped[int] = mapped_column(Integer)
    __table_args__ = (ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id']),
        UniqueConstraint('campaign_id','variant_name',name='uq_campaign_variant_name'),
        CheckConstraint("variant_name IN ('A','B')",name='name'), CheckConstraint('allocation_bp > 0 AND allocation_bp < 10000',name='allocation'))


class CampaignExclusion(IdentityMixin, Base):
    __tablename__ = 'campaign_exclusions'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    campaign_id: Mapped[UUID]
    segment_revision_id: Mapped[UUID]
    __table_args__ = (ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id']),
        ForeignKeyConstraint(['dataset_id','segment_revision_id'],['segment_revisions.dataset_id','segment_revisions.id']),
        UniqueConstraint('campaign_id','segment_revision_id',name='uq_campaign_exclusion'))
