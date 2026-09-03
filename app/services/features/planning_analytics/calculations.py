"""
Feature: Calendar-based priority and workload calculations.

Responsibilities:
- Calculate weekday-capacity work hours without using estimated_hours.
- Derive remaining-hours, overdue-days, and documented pressure bands.

Does not own: holiday administration, database persistence, authorization, or UI labels.
Plan task: DEV-14.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
import math
from zoneinfo import ZoneInfo

EXECUTION_TASK_STATUSES = frozenset({"in_progress", "blocked", "pending_report"})
HOURS_QUANT = Decimal("0.01")
BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


def aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(UTC)


def working_hours_between(
    start: datetime,
    end: datetime,
    *,
    daily_capacity_hours: Decimal | int | float = Decimal("8"),
) -> Decimal:
    """Return weekday capacity hours for a time window.

    The current schema has no holiday/shift table. DEV-14 therefore uses a
    deterministic Asia/Shanghai weekday-capacity calendar: weekends contribute
    zero and each weekday contributes daily_capacity_hours proportionally across its 24-hour
    calendar window. This avoids inventing an unapproved 09:00/18:00 shift while
    keeping a full weekday equal to the configured daily capacity. A future
    holiday/shift calendar can replace this function without changing callers.
    """
    start_local = aware_utc(start).astimezone(BUSINESS_TIMEZONE)
    end_local = aware_utc(end).astimezone(BUSINESS_TIMEZONE)
    capacity = Decimal(str(daily_capacity_hours))
    if end_local <= start_local or capacity <= 0:
        return Decimal("0.00")
    cursor = start_local.date()
    end_date = end_local.date()
    total = Decimal("0")
    while cursor <= end_date:
        if cursor.weekday() < 5:
            day_start = datetime.combine(cursor, time.min, tzinfo=BUSINESS_TIMEZONE)
            day_end = day_start + timedelta(days=1)
            interval_start = max(start_local, day_start)
            interval_end = min(end_local, day_end)
            if interval_end > interval_start:
                elapsed = Decimal(str((interval_end - interval_start).total_seconds())) / Decimal("3600")
                total += elapsed / Decimal("24") * capacity
        cursor += timedelta(days=1)
    return total.quantize(HOURS_QUANT, rounding=ROUND_HALF_UP)


def remaining_hours(
    *,
    start_time: datetime | None,
    deadline: datetime | None,
    now: datetime,
    daily_capacity_hours: Decimal | int | float = Decimal("8"),
) -> Decimal | None:
    if deadline is None:
        return None
    now_utc = aware_utc(now)
    deadline_utc = aware_utc(deadline)
    if now_utc >= deadline_utc:
        return Decimal("0.00")
    start = aware_utc(start_time) if start_time is not None else now_utc
    effective_start = start if now_utc < start else now_utc
    return working_hours_between(
        effective_start,
        deadline_utc,
        daily_capacity_hours=daily_capacity_hours,
    )


def overdue_days(
    deadline: datetime | None,
    now: datetime,
    *,
    daily_capacity_hours: Decimal | int | float = Decimal("8"),
) -> int:
    if deadline is None or aware_utc(now) <= aware_utc(deadline):
        return 0
    capacity = Decimal(str(daily_capacity_hours))
    if capacity <= 0:
        return 0
    overdue_hours = working_hours_between(
        deadline,
        now,
        daily_capacity_hours=capacity,
    )
    # A task already past its deadline is at least one overdue day even when the
    # elapsed time falls entirely on a weekend/non-working window.
    return max(1, int(math.ceil(float(overdue_hours / capacity))))


def time_pressure_score(value: Decimal | None, *, overdue: bool) -> Decimal:
    if overdue:
        return Decimal("100")
    if value is None:
        return Decimal("0")
    if value <= 8:
        return Decimal("90")
    if value <= 24:
        return Decimal("75")
    if value <= 56:
        return Decimal("50")
    return Decimal("25")


def overdue_pressure_score(days: int) -> Decimal:
    if days <= 0:
        return Decimal("0")
    if days == 1:
        return Decimal("60")
    if days <= 3:
        return Decimal("80")
    return Decimal("100")


def workload_level(score: Decimal | int | float) -> str:
    value = Decimal(str(score))
    if value <= 40:
        return "idle"
    if value <= 70:
        return "normal"
    if value <= 90:
        return "busy"
    return "overloaded"
