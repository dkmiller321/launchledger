"""Injected clock: FROZEN_TODAY pins the date so 'late' is stable in tests and demos."""

from datetime import UTC, date, datetime

from launchledger.settings import get_settings


def today() -> date:
    frozen = get_settings().frozen_today
    return frozen if frozen is not None else datetime.now(UTC).date()


def now() -> datetime:
    """Current time; with FROZEN_TODAY the date is pinned and the time of day is real."""
    real = datetime.now(UTC)
    frozen = get_settings().frozen_today
    if frozen is None:
        return real
    return real.replace(year=frozen.year, month=frozen.month, day=frozen.day)
