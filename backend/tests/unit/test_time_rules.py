from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.utils.time import (
    ReservationTimeError,
    calculate_reservation_end,
    is_allowed_reservation_start,
    normalize_to_seoul,
    validate_reservation_start,
)


SEOUL = ZoneInfo("Asia/Seoul")


def seoul_datetime(hour: int, minute: int = 0, day: int = 25) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=SEOUL)


def test_normalize_to_seoul_converts_offsets() -> None:
    utc_time = datetime.fromisoformat("2026-06-25T09:00:00+00:00")

    result = normalize_to_seoul(utc_time)

    assert result == datetime(2026, 6, 25, 18, 0, tzinfo=SEOUL)


def test_calculate_reservation_end_blocks_exactly_100_minutes() -> None:
    start = seoul_datetime(18, 10)

    result = calculate_reservation_end(start)

    assert result == seoul_datetime(19, 50)


@pytest.mark.parametrize(
    ("hour", "minute"),
    [
        (11, 0),
        (13, 17),
        (14, 30),
        (17, 0),
        (18, 10),
        (19, 30),
    ],
)
def test_allowed_reservation_start_windows_accept_exact_minutes(hour: int, minute: int) -> None:
    assert is_allowed_reservation_start(seoul_datetime(hour, minute)) is True


@pytest.mark.parametrize(
    ("hour", "minute"),
    [
        (10, 59),
        (14, 31),
        (16, 0),
        (16, 59),
        (19, 31),
        (21, 0),
    ],
)
def test_allowed_reservation_start_windows_reject_invalid_times(hour: int, minute: int) -> None:
    assert is_allowed_reservation_start(seoul_datetime(hour, minute)) is False


def test_validate_reservation_start_rejects_past_times() -> None:
    now = seoul_datetime(18, 0)

    with pytest.raises(ReservationTimeError, match="past"):
        validate_reservation_start(seoul_datetime(17, 59), now=now)


def test_validate_reservation_start_rejects_outside_reservation_windows() -> None:
    now = seoul_datetime(12, 0, day=24)

    with pytest.raises(ReservationTimeError, match="outside reservation hours"):
        validate_reservation_start(seoul_datetime(14, 31), now=now)
