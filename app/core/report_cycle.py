"""Test14: shared report-cycle format contract for HTTP and task/AI boundaries.

No recurrence calculation, defaults, persistence, or database schema changes.
The regular expression mirrors the existing PostgreSQL CHECK constraint.
"""
import re

REPORT_CYCLE_RE = re.compile(
    r"^weekly:(MON|TUE|WED|THU|FRI|SAT|SUN)@([01][0-9]|2[0-3]):[0-5][0-9]$"
)
REPORT_CYCLE_ERROR = (
    "report_cycle must be null or weekly:DAY@HH:MM "
    "(DAY=MON/TUE/WED/THU/FRI/SAT/SUN, HH=00-23, MM=00-59)"
)


def is_valid_report_cycle(value: object) -> bool:
    """Do not coerce incomplete human/AI text into invented recurrence facts."""
    return value is None or (
        isinstance(value, str) and REPORT_CYCLE_RE.fullmatch(value) is not None
    )


def validate_report_cycle(value: str | None) -> str | None:
    if not is_valid_report_cycle(value):
        raise ValueError(REPORT_CYCLE_ERROR)
    return value
