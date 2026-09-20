from datetime import datetime
from uuid import UUID
from sqlalchemy import String, DateTime, ForeignKey, Integer, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, IdentityMixin


class AICopyCache(Base):
    __tablename__ = 'ai_copy_cache'
    cache_key: Mapped[str] = mapped_column(String(64),primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id',ondelete='CASCADE'),index=True)
    generated: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AIActionProposal(IdentityMixin, Base):
    __tablename__ = 'ai_action_proposals'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    payload: Mapped[dict] = mapped_column(JSONB)
    payload_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    segment_id: Mapped[UUID | None]
    action_type: Mapped[str] = mapped_column(String(30),default='SEGMENT',server_default='SEGMENT')
    campaign_id: Mapped[UUID | None]
    data_version: Mapped[int | None] = mapped_column(Integer)
    policy_version: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (ForeignKeyConstraint(['dataset_id', 'segment_id'], ['segments.dataset_id', 'segments.id']),
        ForeignKeyConstraint(['dataset_id','campaign_id'],['campaigns.dataset_id','campaigns.id']))


class AIExecutionLog(IdentityMixin, Base):
    __tablename__ = 'ai_execution_logs'
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey('datasets.id'))
    request_id: Mapped[UUID]
    actor_type: Mapped[str] = mapped_column(String(20), default='VISITOR')
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(20), default='ai-a-1')
    status: Mapped[str] = mapped_column(String(30))
    tool_name: Mapped[str | None] = mapped_column(String(50))
    elapsed_ms: Mapped[int] = mapped_column(Integer)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
