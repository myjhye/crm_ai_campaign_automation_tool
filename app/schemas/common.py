from datetime import datetime
from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer, field_validator,
    model_validator,
)

from app.core.time import as_utc

Money = Annotated[
    Decimal,
    Field(ge=0, allow_inf_nan=False),
    PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json"),
]
T = TypeVar("T")


class Pagination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class ReportingPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")

    @field_validator("start", "end")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @model_validator(mode="after")
    def validate_order(self) -> "ReportingPeriod":
        if self.end <= self.start:
            raise ValueError("Period must have a positive duration")
        return self

    def contains(self, value: datetime) -> bool:
        return self.start <= as_utc(value) < self.end

    def previous(self) -> "ReportingPeriod":
        return ReportingPeriod(start=self.start - (self.end - self.start), end=self.start)
