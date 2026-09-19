from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Pagination

ActorType = Literal["VISITOR", "AI", "SYSTEM"]


class AuditFilters(Pagination):
    dataset_id: UUID | None = None
    resource_id: UUID | None = None
    actor_type: ActorType | None = None
    action: str | None = Field(default=None, min_length=1, max_length=80)


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    dataset_id: UUID
    resource_id: UUID | None
    actor_type: ActorType
    action: str
    request_id: UUID | None
    previous_version: int | None
    new_version: int | None
    created_at: datetime
