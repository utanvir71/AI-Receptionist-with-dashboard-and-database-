"""Reservation service notification behavior."""

from datetime import datetime
import logging

import pytest

from app.models.resources import SeatingPreference
from app.schemas.reservations import (
    CancelReservationRequest,
    CreateReservationRequest,
    ModifyReservationRequest,
    VapiToolStatus,
)
from app.services.calendar_service import InMemoryCalendarService, ReservationRecord
from app.services.reservation_service import ReservationService
from app.utils.time import SEOUL_TZ


NOW = datetime(2026, 6, 25, 10, 0, tzinfo=SEOUL_TZ)


def seoul_datetime(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SEOUL_TZ)


class RecordingReservationNotifier:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.confirmations: list[ReservationRecord] = []
        self.modifications: list[ReservationRecord] = []
        self.cancellations: list[ReservationRecord] = []

    def send_confirmation(self, record: ReservationRecord) -> None:
        if self.fail_on == "confirmation":
            raise RuntimeError("twilio unavailable")
        self.confirmations.append(record)

    def send_modification(self, record: ReservationRecord) -> None:
        if self.fail_on == "modification":
            raise RuntimeError("twilio unavailable")
        self.modifications.append(record)

    def send_cancellation(self, record: ReservationRecord) -> None:
        if self.fail_on == "cancellation":
            raise RuntimeError("twilio unavailable")
        self.cancellations.append(record)


@pytest.fixture
def calendar() -> InMemoryCalendarService:
    return InMemoryCalendarService()


def service(
    calendar: InMemoryCalendarService,
    notifier: RecordingReservationNotifier,
) -> ReservationService:
    return ReservationService(
        calendar=calendar,
        notifier=notifier,
        now_provider=lambda: NOW,
    )


def create_request(
    *,
    party_size: int = 2,
    reservation_start: datetime | None = None,
    phone: str = "+821012345678",
    name: str = "Jane Kim",
) -> CreateReservationRequest:
    return CreateReservationRequest(
        customer_name=name,
        phone=phone,
        party_size=party_size,
        reservation_start=reservation_start or seoul_datetime(2026, 7, 1, 18),
        seating_preference=SeatingPreference.NO_PREFERENCE,
    )


def test_create_reservation_sends_confirmation_after_calendar_success(
    calendar: InMemoryCalendarService,
) -> None:
    notifier = RecordingReservationNotifier()
    reservation_service = service(calendar, notifier)

    response = reservation_service.create_reservation(create_request())

    assert response.status == VapiToolStatus.CONFIRMED
    assert len(calendar.records) == 1
    assert notifier.confirmations == [calendar.records[0]]


def test_confirmation_sms_failure_is_logged_without_unconfirming_reservation(
    calendar: InMemoryCalendarService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    notifier = RecordingReservationNotifier(fail_on="confirmation")
    reservation_service = service(calendar, notifier)
    caplog.set_level(logging.WARNING, logger="app.services.reservation_service")

    response = reservation_service.create_reservation(create_request())

    assert response.status == VapiToolStatus.CONFIRMED
    assert response.message == "Reservation confirmed."
    assert len(calendar.records) == 1
    assert calendar.records[0].status == "confirmed"
    assert "SMS confirmation failed for reservation" in caplog.text


def test_modify_reservation_sends_modification_sms_after_update(
    calendar: InMemoryCalendarService,
) -> None:
    notifier = RecordingReservationNotifier()
    reservation_service = service(calendar, notifier)
    reservation_service.create_reservation(create_request())

    response = reservation_service.modify_reservation(
        ModifyReservationRequest(
            phone="+821012345678",
            original_reservation_start=seoul_datetime(2026, 7, 1, 18),
            new_reservation_start=seoul_datetime(2026, 7, 1, 19),
        )
    )

    assert response.status == VapiToolStatus.CONFIRMED
    assert notifier.modifications == [calendar.records[0]]


def test_cancel_reservation_sends_cancellation_sms_after_update(
    calendar: InMemoryCalendarService,
) -> None:
    notifier = RecordingReservationNotifier()
    reservation_service = service(calendar, notifier)
    reservation_service.create_reservation(create_request())

    response = reservation_service.cancel_reservation(
        CancelReservationRequest(
            phone="+821012345678",
            reservation_start=seoul_datetime(2026, 7, 1, 18),
        )
    )

    assert response.status == VapiToolStatus.CANCELLED
    assert notifier.cancellations == [calendar.records[0]]


def test_cancellation_sms_failure_is_logged_without_uncancelling_reservation(
    calendar: InMemoryCalendarService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    notifier = RecordingReservationNotifier(fail_on="cancellation")
    reservation_service = service(calendar, notifier)
    reservation_service.create_reservation(create_request())
    caplog.set_level(logging.WARNING, logger="app.services.reservation_service")

    response = reservation_service.cancel_reservation(
        CancelReservationRequest(
            phone="+821012345678",
            reservation_start=seoul_datetime(2026, 7, 1, 18),
        )
    )

    assert response.status == VapiToolStatus.CANCELLED
    assert calendar.records[0].status == "cancelled"
    assert "SMS cancellation failed for reservation" in caplog.text
