from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from decimal import Decimal, InvalidOperation
from app.schemas.analytics import AnalyticsQuery
from typing import Literal


class CampaignBrief(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    segment_revision_id: UUID
    name: str = Field(min_length=1,max_length=200)
    objective: str = Field(min_length=1,max_length=500)
    channel: Literal['EMAIL','PUSH','SMS']
    benefit: str = Field(min_length=1,max_length=1000)
    brand_tone: str = Field(min_length=1,max_length=200)
    primary_kpi: Literal['click_rate','conversion_rate','revenue'] = 'conversion_rate'
    target_value: str = '5.00'
    coupon_expires_at: AwareDatetime | None = None


class CampaignSetup(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    segment_revision_id: UUID
    channel: Literal['EMAIL','PUSH','SMS'] = 'EMAIL'
    benefit: str = Field(min_length=1,max_length=1000)
    objective: str = Field(default='재구매 유도',min_length=1,max_length=500)
    brand_tone: str = Field(default='다정하고 편안하게',min_length=1,max_length=200)
    primary_kpi: Literal['conversion_rate','click_rate','revenue'] = 'conversion_rate'
    target_value: str = '5.00'
    a_focus: str = Field(default='혜택 강조',min_length=1,max_length=200)
    b_focus: str = Field(default='관계 강조',min_length=1,max_length=200)

    @model_validator(mode='after')
    def validate_target(self):
        try:value=Decimal(self.target_value)
        except InvalidOperation:raise ValueError('KPI 목표값을 숫자로 입력해주세요.') from None
        if not value.is_finite() or value<0 or value>=Decimal('10000000000000000') or value.as_tuple().exponent < -2:
            raise ValueError('KPI 목표값의 범위와 소수 자릿수를 확인해주세요.')
        if self.primary_kpi!='revenue' and value>100:
            raise ValueError('비율 목표는 0~100입니다.')
        if self.a_focus==self.b_focus:raise ValueError('A/B 강조점은 다르게 선택해주세요.')
        return self


class ChatRequest(AnalyticsQuery):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=1, max_length=2000)
    reference_at: AwareDatetime
    campaign_brief: CampaignBrief | None = None
    campaign_setup: CampaignSetup | None = None
    campaign_id: UUID | None = None
    campaign_version: int | None = Field(default=None,ge=1,strict=True)
    validation_campaign_id: UUID | None = None
    validation_campaign_version: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode='after')
    def validation_context(self):
        if (self.validation_campaign_id is None) != (self.validation_campaign_version is None):
            raise ValueError('검수 캠페인 ID와 버전을 함께 입력해주세요.')
        if self.validation_campaign_id and (self.campaign_id or self.campaign_brief or self.campaign_setup):
            raise ValueError('캠페인 생성과 검수를 한 요청에 함께 지정할 수 없습니다.')
        return self


class Confirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dataset_id: UUID
