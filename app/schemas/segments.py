from uuid import UUID
from pydantic import BaseModel, ConfigDict, AwareDatetime, Field, field_validator
from app.core.time import as_utc
from app.domain.segments.dsl import Condition, check_limits
from app.schemas.common import Pagination
from app.schemas.datasets import DatasetName

class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: UUID
    condition: Condition
    reference_at: AwareDatetime
    data_version: int | None = Field(default=None, ge=0)

    @field_validator('condition')
    @classmethod
    def bounded(cls, value):
        check_limits(value)
        return value

    @field_validator('reference_at')
    @classmethod
    def utc(cls, value): return as_utc(value)

class SegmentWrite(PreviewRequest):
    name: DatasetName

class SegmentUpdate(SegmentWrite):
    version: int = Field(ge=1, strict=True)

class SegmentList(Pagination):
    dataset_id: UUID

class SegmentArchive(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: UUID
    version: int = Field(ge=1, strict=True)
