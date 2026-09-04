from collections.abc import Callable
from datetime import datetime, UTC

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """Return an aware UTC timestamp suitable for business events."""

    return datetime.now(UTC)
