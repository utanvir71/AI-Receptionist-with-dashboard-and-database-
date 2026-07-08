"""Google Calendar storage boundary behavior."""

from datetime import datetime

from app.models.resources import SeatingPreference
from app.core.config import Settings
from app.services.calendar_service import (
    CANCELLED_STATUS,
    GoogleCalendarService,
    ReservationRecord,
    build_google_calendar_service,
)
from app.utils.time import SEOUL_TZ


def seoul_datetime(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SEOUL_TZ)


class FakeGoogleRequest:
    def __init__(self, response: object) -> None:
        self.response = response

    def execute(self) -> object:
        return self.response


class FakeGoogleEvents:
    def __init__(self) -> None:
        self.insert_calls: list[dict[str, object]] = []
        self.patch_calls: list[dict[str, object]] = []
        self.list_calls: list[dict[str, object]] = []
        self.insert_response: dict[str, object] = {"id": "event-created"}
        self.patch_response: dict[str, object] = {"id": "event-updated"}
        self.list_response: dict[str, object] = {"items": []}

    def insert(self, **kwargs: object) -> FakeGoogleRequest:
        self.insert_calls.append(kwargs)
        return FakeGoogleRequest(self.insert_response)

    def patch(self, **kwargs: object) -> FakeGoogleRequest:
        self.patch_calls.append(kwargs)
        return FakeGoogleRequest(self.patch_response)

    def list(self, **kwargs: object) -> FakeGoogleRequest:
        self.list_calls.append(kwargs)
        return FakeGoogleRequest(self.list_response)


def reservation_record(**overrides: object) -> ReservationRecord:
    values = {
        "customer_name": "Jane Kim",
        "phone": "+821012345678",
        "party_size": 4,
        "start": seoul_datetime(2026, 7, 1, 18),
        "end": seoul_datetime(2026, 7, 1, 19, 40),
        "seating_preference": SeatingPreference.WINDOW_SIDE,
        "resource_ids": ("table_3",),
        "notes": "birthday",
        "allergy_notes": "peanut allergy",
        "call_id": "call-123",
        "private_room_minimum_spend_krw": None,
        "id": "existing-id",
    }
    values.update(overrides)
    return ReservationRecord(**values)


def test_create_reservation_writes_human_description_and_private_metadata() -> None:
    events = FakeGoogleEvents()
    calendar = GoogleCalendarService(events=events, calendar_id="calendar-123")
    record = reservation_record(id="")

    created = calendar.create_reservation(record)

    assert created.id == "event-created"
    body = events.insert_calls[0]["body"]
    assert body["summary"] == "4 guests - Jane Kim"
    assert body["start"] == {"dateTime": "2026-07-01T18:00:00+09:00", "timeZone": "Asia/Seoul"}
    assert body["end"] == {"dateTime": "2026-07-01T19:40:00+09:00", "timeZone": "Asia/Seoul"}
    assert body["extendedProperties"]["private"] == {
        "customer_name": "Jane Kim",
        "phone": "+821012345678",
        "party_size": "4",
        "seating_preference": "window_side",
        "resource_ids": "table_3",
        "notes": "birthday",
        "allergy_notes": "peanut allergy",
        "call_id": "call-123",
        "private_room_minimum_spend_krw": "",
        "booking_status": "confirmed",
    }
    assert "Customer: Jane Kim" in body["description"]
    assert "Internal resource: table_3" in body["description"]


def test_list_reservations_reads_metadata_and_ignores_cancelled_events() -> None:
    events = FakeGoogleEvents()
    events.list_response = {
        "items": [
            google_event(id="active-event", booking_status="confirmed"),
            google_event(id="cancelled-event", booking_status=CANCELLED_STATUS),
        ]
    }
    calendar = GoogleCalendarService(events=events, calendar_id="calendar-123")

    records = calendar.list_reservations(
        start=seoul_datetime(2026, 7, 1, 17),
        end=seoul_datetime(2026, 7, 1, 20),
    )

    assert len(records) == 1
    assert records[0].id == "active-event"
    assert records[0].customer_name == "Jane Kim"
    assert records[0].resource_ids == ("table_3",)
    assert events.list_calls[0]["calendarId"] == "calendar-123"
    assert events.list_calls[0]["timeMin"] == "2026-07-01T17:00:00+09:00"
    assert events.list_calls[0]["timeMax"] == "2026-07-01T20:00:00+09:00"
    assert events.list_calls[0]["singleEvents"] is True


def test_find_reservations_matches_phone_start_and_optional_customer_name() -> None:
    events = FakeGoogleEvents()
    events.list_response = {
        "items": [
            google_event(id="match", customer_name="Jane Kim", phone="+821012345678"),
            google_event(id="wrong-phone", customer_name="Jane Kim", phone="+821099999999"),
            google_event(id="wrong-name", customer_name="Other Guest", phone="+821012345678"),
        ]
    }
    calendar = GoogleCalendarService(events=events, calendar_id="calendar-123")

    records = calendar.find_reservations(
        phone="+821012345678",
        reservation_start=seoul_datetime(2026, 7, 1, 18),
        customer_name="Jane Kim",
    )

    assert [record.id for record in records] == ["match"]


def test_update_reservation_patches_existing_event_and_can_mark_cancelled() -> None:
    events = FakeGoogleEvents()
    calendar = GoogleCalendarService(events=events, calendar_id="calendar-123")
    record = reservation_record(status=CANCELLED_STATUS)

    updated = calendar.update_reservation(record)

    assert updated.id == "existing-id"
    patch_call = events.patch_calls[0]
    assert patch_call["calendarId"] == "calendar-123"
    assert patch_call["eventId"] == "existing-id"
    assert patch_call["body"]["extendedProperties"]["private"]["booking_status"] == "cancelled"


def test_build_google_calendar_service_uses_service_account_file(
    monkeypatch: object,
) -> None:
    calls: dict[str, object] = {}

    class FakeCredentials:
        @classmethod
        def from_service_account_file(cls, path: str, scopes: list[str]) -> str:
            calls["credential_path"] = path
            calls["scopes"] = scopes
            return "credentials"

    class FakeDiscovery:
        @staticmethod
        def build(service_name: str, version: str, credentials: str) -> object:
            calls["service_name"] = service_name
            calls["version"] = version
            calls["credentials"] = credentials
            return type("FakeCalendarApi", (), {"events": lambda self: "events-resource"})()

    monkeypatch.setattr(
        "app.services.calendar_service.service_account.Credentials",
        FakeCredentials,
    )
    monkeypatch.setattr("app.services.calendar_service.google_discovery", FakeDiscovery)

    calendar = build_google_calendar_service(
        Settings(
            google_calendar_id="calendar-123",
            google_application_credentials="/private/service-account.json",
        )
    )

    assert isinstance(calendar, GoogleCalendarService)
    assert calls == {
        "credential_path": "/private/service-account.json",
        "scopes": ["https://www.googleapis.com/auth/calendar.events"],
        "service_name": "calendar",
        "version": "v3",
        "credentials": "credentials",
    }


def google_event(
    *,
    id: str,
    customer_name: str = "Jane Kim",
    phone: str = "+821012345678",
    booking_status: str = "confirmed",
) -> dict[str, object]:
    return {
        "id": id,
        "start": {"dateTime": "2026-07-01T18:00:00+09:00"},
        "end": {"dateTime": "2026-07-01T19:40:00+09:00"},
        "extendedProperties": {
            "private": {
                "customer_name": customer_name,
                "phone": phone,
                "party_size": "4",
                "seating_preference": "window_side",
                "resource_ids": "table_3",
                "notes": "birthday",
                "allergy_notes": "peanut allergy",
                "call_id": "call-123",
                "private_room_minimum_spend_krw": "",
                "booking_status": booking_status,
            }
        },
    }
