"""Reservation service behavior using the in-memory calendar fake."""

from datetime import datetime

import pytest

from app.models.resources import SeatingPreference
from app.schemas.reservations import (
    CancelReservationRequest,
    CheckAvailabilityRequest,
    CreateReservationRequest,
    ModifyReservationRequest,
    SearchReservationRequest,
    VapiToolStatus,
)
from app.services.calendar_service import InMemoryCalendarService
from app.services.reservation_service import ReservationService
from app.utils.time import SEOUL_TZ


NOW = datetime(2026, 6, 25, 10, 0, tzinfo=SEOUL_TZ)


def seoul_datetime(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SEOUL_TZ)


@pytest.fixture
def service() -> ReservationService:
    calendar = InMemoryCalendarService()
    return ReservationService(calendar=calendar, now_provider=lambda: NOW)


def create_request(
    *,
    party_size: int = 2,
    reservation_start: datetime | None = None,
    seating_preference: SeatingPreference = SeatingPreference.NO_PREFERENCE,
    phone: str = "+821012345678",
    name: str = "Jane Kim",
) -> CreateReservationRequest:
    return CreateReservationRequest(
        customer_name=name,
        phone=phone,
        party_size=party_size,
        reservation_start=reservation_start or seoul_datetime(2026, 7, 1, 12),
        seating_preference=seating_preference,
        notes="birthday",
        allergy_notes="peanut allergy",
        call_id="call-123",
    )


def test_create_reservation_stores_confirmed_record_and_search_finds_it(
    service: ReservationService,
) -> None:
    request = create_request()

    response = service.create_reservation(request)

    assert response.status == VapiToolStatus.CONFIRMED
    assert response.message == "Reservation confirmed."
    assert response.data["reservation_id"]
    assert response.data["reservation_start"] == "2026-07-01T12:00:00+09:00"
    assert response.data["reservation_end"] == "2026-07-01T13:40:00+09:00"

    search_response = service.search_reservation(
        SearchReservationRequest(
            phone="+821012345678",
            reservation_start=seoul_datetime(2026, 7, 1, 12),
        )
    )

    assert search_response.status == VapiToolStatus.CONFIRMED
    assert search_response.data["customer_name"] == "Jane Kim"
    assert search_response.data["party_size"] == 2
    assert search_response.data["status"] == "confirmed"


def test_create_reservation_rejects_duplicate_only_resource_and_suggests_nearby_time(
    service: ReservationService,
) -> None:
    reservation_start = seoul_datetime(2026, 7, 1, 12)
    first_response = service.create_reservation(
        create_request(party_size=8, reservation_start=reservation_start)
    )
    assert first_response.status == VapiToolStatus.CONFIRMED

    response = service.create_reservation(
        create_request(
            party_size=8,
            reservation_start=reservation_start,
            phone="+821099999999",
            name="Duplicate Caller",
        )
    )

    assert response.status == VapiToolStatus.UNAVAILABLE
    assert response.message == "That time is not available."
    assert response.data["nearby_options"] == ["2026-07-01T14:00:00+09:00"]
    assert response.data["loop_policy"] == "offer_nearby_once_then_ask_new_datetime"


def test_cancelled_reservation_is_kept_but_does_not_block_rebooking(
    service: ReservationService,
) -> None:
    reservation_start = seoul_datetime(2026, 7, 1, 12)
    created = service.create_reservation(
        create_request(party_size=8, reservation_start=reservation_start)
    )
    assert created.status == VapiToolStatus.CONFIRMED

    cancelled = service.cancel_reservation(
        CancelReservationRequest(
            phone="+821012345678",
            reservation_start=reservation_start,
        )
    )
    assert cancelled.status == VapiToolStatus.CANCELLED
    assert cancelled.message == "Reservation cancelled."

    replacement = service.create_reservation(
        create_request(
            party_size=8,
            reservation_start=reservation_start,
            phone="+821011111111",
            name="Replacement Caller",
        )
    )

    assert replacement.status == VapiToolStatus.CONFIRMED
    assert len(service.calendar.records) == 2
    assert [record.status for record in service.calendar.records] == ["cancelled", "confirmed"]


def test_modify_reservation_reallocates_when_requested_time_is_available(
    service: ReservationService,
) -> None:
    service.create_reservation(create_request(party_size=8))

    response = service.modify_reservation(
        ModifyReservationRequest(
            phone="+821012345678",
            original_reservation_start=seoul_datetime(2026, 7, 1, 12),
            new_reservation_start=seoul_datetime(2026, 7, 1, 14),
            new_party_size=7,
        )
    )

    assert response.status == VapiToolStatus.CONFIRMED
    assert response.message == "Reservation updated."
    assert response.data["reservation_start"] == "2026-07-01T14:00:00+09:00"
    assert response.data["party_size"] == 7

    old_search = service.search_reservation(
        SearchReservationRequest(
            phone="+821012345678",
            reservation_start=seoul_datetime(2026, 7, 1, 12),
        )
    )
    assert old_search.status == VapiToolStatus.NOT_FOUND


def test_modify_reservation_leaves_original_record_when_new_time_conflicts(
    service: ReservationService,
) -> None:
    service.create_reservation(create_request(party_size=8, reservation_start=seoul_datetime(2026, 7, 1, 12)))
    service.create_reservation(
        create_request(
            party_size=8,
            reservation_start=seoul_datetime(2026, 7, 1, 14),
            phone="+821022222222",
            name="Second Caller",
        )
    )

    response = service.modify_reservation(
        ModifyReservationRequest(
            phone="+821022222222",
            original_reservation_start=seoul_datetime(2026, 7, 1, 14),
            new_reservation_start=seoul_datetime(2026, 7, 1, 12),
        )
    )

    assert response.status == VapiToolStatus.UNAVAILABLE
    assert response.message == "That time is not available."

    still_original = service.search_reservation(
        SearchReservationRequest(
            phone="+821022222222",
            reservation_start=seoul_datetime(2026, 7, 1, 14),
        )
    )
    assert still_original.status == VapiToolStatus.CONFIRMED


def test_private_room_request_includes_minimum_spend_and_large_regular_party_requires_choice(
    service: ReservationService,
) -> None:
    regular_response = service.check_availability(
        CheckAvailabilityRequest(
            party_size=10,
            reservation_start=seoul_datetime(2026, 7, 1, 12),
            seating_preference=SeatingPreference.NO_PREFERENCE,
        )
    )
    assert regular_response.status == VapiToolStatus.PRIVATE_ROOM_REQUIRED
    assert regular_response.data["next_action"] == "ask_private_room_preference"

    private_response = service.create_reservation(
        create_request(
            party_size=10,
            seating_preference=SeatingPreference.PRIVATE_ROOM,
        )
    )
    assert private_response.status == VapiToolStatus.CONFIRMED
    assert private_response.data["private_room_minimum_spend_krw"] == 620_000


def test_more_than_twelve_guests_requires_manager_followup(service: ReservationService) -> None:
    response = service.create_reservation(create_request(party_size=13))

    assert response.status == VapiToolStatus.MANAGER_REQUIRED
    assert response.message == "A manager is required for this request."
    assert response.data["next_action"] == "collect_details_and_transfer_to_manager"
    assert service.calendar.records == []


def test_outside_reservation_window_returns_caller_safe_status(service: ReservationService) -> None:
    response = service.check_availability(
        CheckAvailabilityRequest(
            party_size=2,
            reservation_start=seoul_datetime(2026, 7, 1, 15),
            seating_preference=SeatingPreference.NO_PREFERENCE,
        )
    )

    assert response.status == VapiToolStatus.OUTSIDE_RESERVATION_HOURS
    assert response.message == "Reservations are available from 11:00 to 14:30 and 17:00 to 19:30."
