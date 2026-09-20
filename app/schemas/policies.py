from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, field_validator
from app.core.time import as_utc

class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    dataset_id: UUID
    version: int = Field(ge=1, strict=True)
    daily_limit: int = Field(ge=1, le=20, strict=True)
    weekly_limit: int = Field(ge=1, le=100, strict=True)
    forbidden_phrases: dict[Literal['EMAIL','PUSH','SMS'], list[str]]
    required_phrases: dict[Literal['EMAIL','PUSH','SMS'], list[str]]

    @field_validator('forbidden_phrases','required_phrases')
    @classmethod
    def phrases(cls, value):
        for items in value.values():
            if len(items) > 30 or any(not item or len(item) > 100 for item in items):
                raise ValueError('정책 문구는 채널별 30개, 항목당 100자 이하입니다.')
            if len(items) != len(set(items)): raise ValueError('정책 문구를 중복 입력할 수 없습니다.')
        return value

class ValidationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: UUID
    campaign_version: int = Field(ge=1, strict=True)
    reference_at: AwareDatetime
    @field_validator('reference_at')
    @classmethod
    def utc(cls, value): return as_utc(value)

class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: UUID
    campaign_version: int = Field(ge=1, strict=True)
    validation_run_id: UUID

class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    dataset_id: UUID
    campaign_version: int = Field(ge=1, strict=True)
    approval_id: UUID
    comment: str | None = Field(default=None, max_length=1000)

class ResumeEditing(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: UUID
    campaign_version: int = Field(ge=1, strict=True)
