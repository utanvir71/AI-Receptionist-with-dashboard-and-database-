from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.models.resources import SeatingPreference
from app.schemas.reservations import (
    CancelReservationRequest,
    CheckAvailabilityRequest,
    CreateReservationRequest,
    ManagerFollowupRequest,
    ModifyReservationRequest,
    SearchReservationRequest,
    VapiToolStatus,
)


SEOUL = ZoneInfo("Asia/Seoul")


def test_check_availability_request_normalizes_phone_free_payload() -> None:
    request = CheckAvailabilityRequest(
        party_size=4,
        reservation_start="2026-06-25T18:10:00+09:00",
        seating_preference=SeatingPreference.WINDOW_SIDE,
    )

    assert request.party_size == 4
    assert request.reservation_start == datetime(2026, 6, 25, 18, 10, tzinfo=SEOUL)
    assert request.seating_preference == SeatingPreference.WINDOW_SIDE


def test_create_reservation_request_requires_e164_phone_number() -> None:
    with pytest.raises(ValidationError, match="E.164"):
        CreateReservationRequest(
            customer_name="Tanvir",
            phone="010-1234-5678",
            party_size=4,
            reservation_start="2026-06-25T18:10:00+09:00",
            seating_preference=SeatingPreference.NO_PREFERENCE,
        )


def test_create_reservation_request_strips_customer_name_and_notes() -> None:
    request = CreateReservationRequest(
        customer_name="  Tanvir  ",
        phone="+821012345678",
        party_size=4,
        reservation_start="2026-06-25T18:10:00+09:00",
        seating_preference=SeatingPreference.GENERAL_NOTE,
        notes="  quiet area  ",
        allergy_notes="  peanut allergy  ",
    )

    assert request.customer_name == "Tanvir"
    assert request.notes == "quiet area"
    assert request.allergy_notes == "peanut allergy"


def test_party_size_must_be_between_one_and_99_for_schema_level_validation() -> None:
    with pytest.raises(ValidationError):
        CheckAvailabilityRequest(
            party_size=0,
            reservation_start="2026-06-25T18:10:00+09:00",
            seating_preference=SeatingPreference.NO_PREFERENCE,
        )


def test_search_and_cancel_requests_use_phone_and_start_time() -> None:
    search = SearchReservationRequest(
        phone="+821012345678",
        reservation_start="2026-06-25T18:10:00+09:00",
    )
    cancel = CancelReservationRequest(
        phone="+821012345678",
        reservation_start="2026-06-25T18:10:00+09:00",
    )

    assert search.phone == "+821012345678"
    assert cancel.reservation_start == datetime(2026, 6, 25, 18, 10, tzinfo=SEOUL)


def test_modify_request_requires_at_least_one_change() -> None:
    with pytest.raises(ValidationError, match="at least one change"):
        ModifyReservationRequest(
            phone="+821012345678",
            original_reservation_start="2026-06-25T18:10:00+09:00",
        )


def test_modify_request_accepts_specific_change_fields() -> None:
    request = ModifyReservationRequest(
        phone="+821012345678",
        original_reservation_start="2026-06-25T18:10:00+09:00",
        new_party_size=5,
        new_notes="birthday",
    )

    assert request.new_party_size == 5
    assert request.new_notes == "birthday"


def test_manager_followup_request_requires_reason() -> None:
    request = ManagerFollowupRequest(
        customer_name="Tanvir",
        phone="+821012345678",
        reason="manager transfer failed",
    )

    assert request.reason == "manager transfer failed"


def test_vapi_tool_status_values_are_stable() -> None:
    assert VapiToolStatus.ACCEPTED == "accepted"
    assert VapiToolStatus.UNAUTHORIZED == "unauthorized"
