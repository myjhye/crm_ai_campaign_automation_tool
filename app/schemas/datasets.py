from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

DatasetName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: DatasetName


class DatasetUpdate(DatasetCreate):
    version: int = Field(ge=1, strict=True)


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    source: Literal["DEMO", "UPLOADED", "SIMULATED"]
    version: int
    created_at: datetime
    updated_at: datetime
    reference_at: datetime | None = None
