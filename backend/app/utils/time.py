"""Seoul timezone parsing and reservation-window helpers."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


SEOUL_TZ = ZoneInfo("Asia/Seoul")
RESERVATION_DURATION_MINUTES = 100

MORNING_START = time(11, 0)
MORNING_END = time(14, 30)
EVENING_START = time(17, 0)
EVENING_END = time(19, 30)


class ReservationTimeError(ValueError):
    """Raised when a requested reservation start time is not allowed."""


def normalize_to_seoul(value: datetime) -> datetime:
    """Return a timezone-aware datetime in Asia/Seoul.

    Naive datetimes are treated as Seoul local time because all restaurant
    reservation rules are defined in Seoul time.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=SEOUL_TZ)
    return value.astimezone(SEOUL_TZ)


def calculate_reservation_end(start: datetime) -> datetime:
    """Return the fixed 100-minute reservation end time."""
    return normalize_to_seoul(start) + timedelta(minutes=RESERVATION_DURATION_MINUTES)


def is_allowed_reservation_start(start: datetime) -> bool:
    """Return whether a reservation may start at this exact Seoul time."""
    requested_time = normalize_to_seoul(start).time()
    return (MORNING_START <= requested_time <= MORNING_END) or (
        EVENING_START <= requested_time <= EVENING_END
    )


def validate_reservation_start(start: datetime, *, now: datetime | None = None) -> datetime:
    """Validate and normalize a requested reservation start time."""
    requested_start = normalize_to_seoul(start)
    current_time = normalize_to_seoul(now or datetime.now(SEOUL_TZ))

    if requested_start < current_time:
        raise ReservationTimeError("reservation start is in the past")

    if not is_allowed_reservation_start(requested_start):
        raise ReservationTimeError("reservation start is outside reservation hours")

    return requested_start
