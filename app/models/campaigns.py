from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy import String, Text, Integer, Numeric, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Boolean, Index, text
from sqlalchemy.dialects.postgresql import JSONB
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
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default='DRAFT', server_default='DRAFT')
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    policy_version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    __table_args__ = (
        UniqueConstraint('dataset_id','id',name='uq_campaign_dataset'),
        ForeignKeyConstraint(['dataset_id','segment_revision_id'],['segment_revisions.dataset_id','segment_revisions.id']),
        CheckConstraint("channel IN ('EMAIL','PUSH','SMS')",name='channel'),
        CheckConstraint("status IN ('DRAFT','REVIEW','APPROVED','RUNNING','COMPLETED','CANCELLED')",name='status'),
        CheckConstraint('version > 0 AND policy_version > 0 AND target_value >= 0',name='values'),
        Index('ix_campaigns_dataset_archived','dataset_id','archived_at'))


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


class PolicySetting(IdentityMixin, Base):
    __tablename__ = 'policy_settings'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'), unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    daily_limit: Mapped[int] = mapped_column(Integer, default=1, server_default='1')
    weekly_limit: Mapped[int] = mapped_column(Integer, default=3, server_default='3')
    forbidden_phrases: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    required_phrases: Mapped[dict] = mapped_column(JSONB, default=dict, server_default='{}')
    __table_args__ = (CheckConstraint('version > 0 AND daily_limit > 0 AND weekly_limit > 0', name='values'),)


class CampaignDelivery(IdentityMixin, Base):
    """Policy exposure ledger. Stage 9 will attach run/result details."""
    __tablename__ = 'campaign_deliveries'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    campaign_id: Mapped[UUID]
    customer_id: Mapped[UUID]
    channel: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id']),
        ForeignKeyConstraint(['dataset_id','customer_id'],['customers.dataset_id','customers.id']),
        UniqueConstraint('campaign_id','customer_id',name='uq_campaign_delivery_customer'),
        CheckConstraint("channel IN ('EMAIL','PUSH','SMS')",name='channel'),
        CheckConstraint("status IN ('SENT','FAILED','EXCLUDED')",name='status'),
        Index('ix_campaign_deliveries_customer_sent','dataset_id','customer_id','channel','sent_at'))


class ValidationRun(IdentityMixin, Base):
    __tablename__ = 'validation_runs'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    campaign_id: Mapped[UUID]
    campaign_version: Mapped[int] = mapped_column(Integer)
    segment_revision_id: Mapped[UUID]
    policy_version: Mapped[int] = mapped_column(Integer)
    data_version: Mapped[int] = mapped_column(Integer)
    reference_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(64))
    initial_count: Mapped[int] = mapped_column(Integer)
    eligible_count: Mapped[int] = mapped_column(Integer)
    excluded_count: Mapped[int] = mapped_column(Integer)
    passed: Mapped[bool] = mapped_column(Boolean)
    rules: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]')
    blockers: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id']),
        ForeignKeyConstraint(['dataset_id','segment_revision_id'],['segment_revisions.dataset_id','segment_revisions.id']),
        UniqueConstraint('dataset_id','id',name='uq_validation_run_dataset'),
        CheckConstraint('campaign_version > 0 AND policy_version > 0 AND data_version >= 0',name='versions'),
        CheckConstraint('initial_count >= 0 AND eligible_count >= 0 AND excluded_count >= 0 AND initial_count = eligible_count + excluded_count',name='counts'))


class ValidationRecipient(IdentityMixin, Base):
    __tablename__ = 'validation_recipients'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    validation_run_id: Mapped[UUID]
    customer_id: Mapped[UUID]
    eligible: Mapped[bool] = mapped_column(Boolean)
    primary_reason: Mapped[str | None] = mapped_column(String(50))
    reasons: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]')
    __table_args__ = (
        ForeignKeyConstraint(['dataset_id','validation_run_id'],['validation_runs.dataset_id','validation_runs.id']),
        ForeignKeyConstraint(['dataset_id','customer_id'],['customers.dataset_id','customers.id']),
        UniqueConstraint('validation_run_id','customer_id',name='uq_validation_recipient'))


class Approval(IdentityMixin, Base):
    __tablename__ = 'approvals'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    campaign_id: Mapped[UUID]
    validation_run_id: Mapped[UUID]
    campaign_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='PENDING', server_default='PENDING')
    decision_source: Mapped[str | None] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(String(1000))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id']),
        ForeignKeyConstraint(['dataset_id','validation_run_id'],['validation_runs.dataset_id','validation_runs.id']),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','WITHDRAWN')",name='status'),
        CheckConstraint("decision_source IS NULL OR decision_source IN ('VISITOR','AI','SYSTEM')",name='decision_source'),
        Index('ix_approvals_campaign_created','campaign_id','created_at'),
        Index('uq_approvals_pending_campaign','campaign_id',unique=True,postgresql_where=text("status = 'PENDING'")))
