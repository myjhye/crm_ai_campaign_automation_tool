from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime
from app.schemas.analytics import AnalyticsQuery


class ChatRequest(AnalyticsQuery):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=1, max_length=2000)
    reference_at: AwareDatetime


class Confirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: UUID
