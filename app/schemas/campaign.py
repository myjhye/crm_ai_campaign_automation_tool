import re
from typing import Literal
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator, field_validator
from app.schemas.common import Pagination
from app.domain.campaigns.copy_policy import POLICIES, CURRENT_VERSION
from app.core.time import as_utc


class VariantWrite(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    variant_name: Literal['A','B']
    subject: str = Field(default='', max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    hypothesis: str = Field(min_length=1, max_length=1000)
    allocation_bp: int = Field(gt=0, lt=10000, strict=True)


class CampaignWrite(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    dataset_id: UUID
    segment_revision_id: UUID
    exclusion_revision_ids: list[UUID] = Field(default_factory=list, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=500)
    channel: Literal['EMAIL','PUSH','SMS']
    benefit: str = Field(min_length=1, max_length=1000)
    brand_tone: str = Field(min_length=1, max_length=200)
    primary_kpi: Literal['click_rate','conversion_rate','revenue']
    target_value: Decimal = Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)
    planned_at: AwareDatetime | None = None
    coupon_expires_at: AwareDatetime | None = None
    variants: list[VariantWrite] = Field(min_length=2, max_length=2)

    @field_validator('target_value', mode='before')
    @classmethod
    def string_value(cls, value):
        if not isinstance(value, str): raise ValueError('목표값은 숫자 문자열로 전달해주세요.')
        return value

    @field_validator('planned_at','coupon_expires_at')
    @classmethod
    def normalize(cls, value): return as_utc(value) if value else None

    @model_validator(mode='after')
    def validate_copy(self):
        if {v.variant_name for v in self.variants} != {'A','B'} or sum(v.allocation_bp for v in self.variants) != 10000:
            raise ValueError('A/B 배분 비율 합계는 100%여야 합니다.')
        if len(set(self.exclusion_revision_ids)) != len(self.exclusion_revision_ids) or self.segment_revision_id in self.exclusion_revision_ids:
            raise ValueError('대상과 제외 세그먼트를 중복 지정할 수 없습니다.')
        if self.primary_kpi != 'revenue' and self.target_value > 100: raise ValueError('비율 목표는 100 이하입니다.')
        policy = POLICIES[CURRENT_VERSION][self.channel]
        for variant in self.variants:
            if self.channel != 'SMS' and not variant.subject: raise ValueError('제목을 입력해주세요.')
            if len(variant.subject) > policy['subject_max'] or len(variant.body) > policy['body_max']:
                raise ValueError('채널별 카피 길이 제한을 초과했습니다.')
            text = variant.subject + '\n' + variant.body
            if re.search(r'[{}]|<[^>]+>', text): raise ValueError('개인화 변수와 HTML은 지원하지 않습니다. 일반 텍스트를 입력해주세요.')
            if any(word in text for word in policy['forbidden']) or any(word not in text for word in policy['required']):
                raise ValueError('데모 카피 정책에 맞지 않습니다.')
        return self


class CampaignUpdate(CampaignWrite):
    version: int = Field(ge=1, strict=True)


class CampaignList(Pagination):
    dataset_id: UUID
