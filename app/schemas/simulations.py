from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class SimulateSendRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dataset_id: UUID
    campaign_version: int = Field(ge=1,strict=True)

