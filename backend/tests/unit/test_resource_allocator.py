from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.resources import (
    SeatingPreference,
    private_room_minimum_spend_for_party_size,
)
from app.services.resource_allocator import (
    AllocationStatus,
    ExistingReservation,
    allocate_resource,
    reservations_overlap,
)


SEOUL = ZoneInfo("Asia/Seoul")


def block(hour: int, minute: int = 0) -> tuple[datetime, datetime]:
    start = datetime(2026, 6, 25, hour, minute, tzinfo=SEOUL)
    return start, start + timedelta(minutes=100)


def reservation(resource_ids: tuple[str, ...], hour: int, minute: int = 0) -> ExistingReservation:
    start, end = block(hour, minute)
    return ExistingReservation(resource_ids=resource_ids, start=start, end=end)


@pytest.mark.parametrize(
    ("party_size", "minimum_spend"),
    [
        (1, 320_000),
        (6, 320_000),
        (7, 420_000),
        (8, 420_000),
        (9, 620_000),
        (12, 620_000),
    ],
)
def test_private_room_minimum_spend_mapping(party_size: int, minimum_spend: int) -> None:
    assert private_room_minimum_spend_for_party_size(party_size) == minimum_spend


def test_private_room_minimum_spend_rejects_unsupported_party_sizes() -> None:
    with pytest.raises(ValueError, match="between 1 and 12"):
        private_room_minimum_spend_for_party_size(13)


def test_reservations_overlap_detects_true_overlap_and_allows_touching_edges() -> None:
    existing_start, existing_end = block(17, 0)
    overlapping_start = datetime(2026, 6, 25, 18, 0, tzinfo=SEOUL)
    overlapping_end = overlapping_start + timedelta(minutes=100)
    touching_start = existing_end
    touching_end = touching_start + timedelta(minutes=100)

    assert reservations_overlap(existing_start, existing_end, overlapping_start, overlapping_end)
    assert not reservations_overlap(existing_start, existing_end, touching_start, touching_end)


def test_regular_booking_uses_smallest_suitable_window_side_table_first() -> None:
    start, end = block(18, 0)

    outcome = allocate_resource(
        party_size=4,
        seating_preference=SeatingPreference.NO_PREFERENCE,
        start=start,
        end=end,
        existing_reservations=[],
    )

    assert outcome.status == AllocationStatus.AVAILABLE
    assert outcome.resource is not None
    assert outcome.resource.id == "table_3"


def test_regular_booking_does_not_use_six_seat_table_when_smaller_table_is_available() -> None:
    start, end = block(18, 0)

    outcome = allocate_resource(
        party_size=2,
        seating_preference=SeatingPreference.NO_PREFERENCE,
        start=start,
        end=end,
        existing_reservations=[],
    )

    assert outcome.status == AllocationStatus.AVAILABLE
    assert outcome.resource is not None
    assert outcome.resource.capacity == 3
    assert outcome.resource.id != "table_7"


def test_window_side_request_uses_only_available_regular_window_side_tables() -> None:
    start, end = block(18, 0)
    occupied = [
        reservation(("table_3",), 18, 0),
        reservation(("table_4",), 18, 0),
        reservation(("table_7",), 18, 0),
    ]

    outcome = allocate_resource(
        party_size=4,
        seating_preference=SeatingPreference.WINDOW_SIDE,
        start=start,
        end=end,
        existing_reservations=occupied,
    )

    assert outcome.status == AllocationStatus.UNAVAILABLE
    assert outcome.resource is None


def test_regular_eight_person_booking_uses_only_table_one_and_two_combination() -> None:
    start, end = block(18, 0)

    outcome = allocate_resource(
        party_size=8,
        seating_preference=SeatingPreference.NO_PREFERENCE,
        start=start,
        end=end,
        existing_reservations=[],
    )

    assert outcome.status == AllocationStatus.AVAILABLE
    assert outcome.resource is not None
    assert outcome.resource.id == "tables_1_2"
    assert outcome.resource.members == ("table_1", "table_2")


def test_regular_eight_person_booking_does_not_fallback_to_private_room() -> None:
    start, end = block(18, 0)

    outcome = allocate_resource(
        party_size=8,
        seating_preference=SeatingPreference.NO_PREFERENCE,
        start=start,
        end=end,
        existing_reservations=[reservation(("table_1",), 18, 0)],
    )

    assert outcome.status == AllocationStatus.UNAVAILABLE
    assert outcome.resource is None


def test_regular_nine_to_twelve_person_booking_requires_private_room_choice() -> None:
    start, end = block(18, 0)

    outcome = allocate_resource(
        party_size=9,
        seating_preference=SeatingPreference.NO_PREFERENCE,
        start=start,
        end=end,
        existing_reservations=[],
    )

    assert outcome.status == AllocationStatus.PRIVATE_ROOM_REQUIRED
    assert outcome.resource is None


def test_more_than_twelve_people_requires_manager() -> None:
    start, end = block(18, 0)

    outcome = allocate_resource(
        party_size=13,
        seating_preference=SeatingPreference.PRIVATE_ROOM,
        start=start,
        end=end,
        existing_reservations=[],
    )

    assert outcome.status == AllocationStatus.MANAGER_REQUIRED
    assert outcome.resource is None


def test_private_room_twelve_person_booking_uses_room_one_and_two_combination() -> None:
    start, end = block(18, 0)

    outcome = allocate_resource(
        party_size=12,
        seating_preference=SeatingPreference.PRIVATE_ROOM,
        start=start,
        end=end,
        existing_reservations=[],
    )

    assert outcome.status == AllocationStatus.AVAILABLE
    assert outcome.resource is not None
    assert outcome.resource.id == "rooms_1_2"
    assert outcome.private_room_minimum_spend_krw == 620_000
