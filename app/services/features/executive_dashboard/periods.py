"""
Feature: Executive dashboard reporting periods.
Responsibilities: resolve current and previous week/month half-open windows in Asia/Shanghai.
Does not own: database queries or authorization.
Plan task: DEV-16.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Literal
from zoneinfo import ZoneInfo

BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
ExecutivePeriod = Literal["week", "month"]


@dataclass(frozen=True)
class PeriodWindow:
    period: ExecutivePeriod
    start: datetime
    end: datetime
    previous_start: datetime
    previous_end: datetime


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)


def _previous_month(value: datetime) -> datetime:
    if value.month == 1:
        return value.replace(year=value.year - 1, month=12)
    return value.replace(month=value.month - 1)


def resolve_executive_period(period: ExecutivePeriod, now: datetime) -> PeriodWindow:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(BUSINESS_TIMEZONE)
    if period == "week":
        local_start = (local - timedelta(days=local.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        local_end = local_start + timedelta(days=7)
        previous_start = local_start - timedelta(days=7)
        previous_end = local_start
    elif period == "month":
        local_start = _month_start(local)
        local_end = _next_month(local_start)
        previous_start = _previous_month(local_start)
        previous_end = local_start
    else:
        raise ValueError("period must be week or month")
    return PeriodWindow(
        period=period,
        start=local_start.astimezone(UTC),
        end=local_end.astimezone(UTC),
        previous_start=previous_start.astimezone(UTC),
        previous_end=previous_end.astimezone(UTC),
    )
