"""Bounded references, never conversation transcripts or trusted client summaries."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator, AwareDatetime


class SegmentHint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['segment']
    id: UUID
    revision_id: UUID
    name: str = Field(default='', max_length=200)
    label: str = Field(default='', max_length=250)


class CampaignListHint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['campaign_list']
    campaign_ids: list[UUID] = Field(min_length=1, max_length=10)
    label: str = Field(default='', max_length=250)


ContextHint = Annotated[SegmentHint | CampaignListHint, Field(discriminator='kind')]


class CompareFilter(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['COMPLETED']
    channel: Literal['EMAIL', 'PUSH', 'SMS', 'ANY']
    segment_revision_id: str = Field(max_length=36)
    start: str = Field(alias='from', max_length=40)
    end: str = Field(alias='to', max_length=40)

    @model_validator(mode='after')
    def paired_period(self):
        if bool(self.start) != bool(self.end):
            raise ValueError('기간 시작과 종료를 함께 지정해주세요.')
        if self.segment_revision_id:
            UUID(self.segment_revision_id)
        return self


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filter: CompareFilter
    sort: Literal['conversion_rate', 'click_rate', 'revenue', 'sent_count']
    order: Literal['desc', 'asc']
    limit: int = Field(ge=1, le=10, strict=True)


class PromptAction(BaseModel):
    label: str
    prefill_prompt: str


class NavigateAction(BaseModel):
    label: str
    action: Literal['navigate']
    campaign_id: UUID


class InsightCard(BaseModel):
    id: str
    kind: Literal['metric','segment_candidate','campaign_performance']
    title: str
    primary_value: str
    secondary_value: str
    cta: PromptAction | NavigateAction


class InsightsResponse(BaseModel):
    dataset_id: UUID
    reference_at: AwareDatetime
    cards: list[InsightCard]
