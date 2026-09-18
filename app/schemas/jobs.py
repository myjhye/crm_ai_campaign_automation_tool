from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    kind: str
    status: Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]
    attempt: int
    max_attempts: int
    progress: int
    created_at: datetime
    available_at: datetime
    heartbeat_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    result: dict | None
