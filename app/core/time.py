"""Timezone-aware reference times and half-open reporting periods."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone is required")
    return value.astimezone(timezone.utc)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    def __init__(self, value: datetime):
        self.value = as_utc(value)

    def now(self) -> datetime:
        return self.value


def inclusive_dates_to_utc(
    start: date, end: date, timezone_name: str = "Asia/Seoul"
) -> tuple[datetime, datetime]:
    if end < start:
        raise ValueError("End date must not precede start date")
    zone = ZoneInfo(timezone_name)
    return (
        as_utc(datetime.combine(start, time.min, zone)),
        as_utc(datetime.combine(end + timedelta(days=1), time.min, zone)),
    )
