"""Calendar storage boundary.

The in-memory implementation is used for local tests and Session 3 behavior.
Session 4 will add a Google Calendar-backed implementation behind this same
service boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from typing import Any, Protocol
from uuid import uuid4

from google.oauth2 import service_account
from googleapiclient import discovery as google_discovery

from app.core.config import Settings
from app.models.resources import SeatingPreference
from app.services.resource_allocator import reservations_overlap
from app.utils.time import normalize_to_seoul


CONFIRMED_STATUS = "confirmed"
CANCELLED_STATUS = "cancelled"
GOOGLE_CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"


@dataclass
class ReservationRecord:
    """Internal reservation record stored by the calendar boundary."""

    customer_name: str
    phone: str
    party_size: int
    start: datetime
    end: datetime
    seating_preference: SeatingPreference
    resource_ids: tuple[str, ...]
    notes: str | None = None
    allergy_notes: str | None = None
    call_id: str | None = None
    private_room_minimum_spend_krw: int | None = None
    status: str = CONFIRMED_STATUS
    id: str = ""

    def __post_init__(self) -> None:
        self.start = normalize_to_seoul(self.start)
        self.end = normalize_to_seoul(self.end)
        if not self.id:
            self.id = uuid4().hex


class ReservationCalendar(Protocol):
    """Storage operations required by the reservation service."""

    def create_reservation(self, record: ReservationRecord) -> ReservationRecord:
        """Persist a new reservation record."""
        ...

    def update_reservation(self, record: ReservationRecord) -> ReservationRecord:
        """Persist changes to an existing reservation record."""
        ...

    def list_reservations(self, *, start: datetime, end: datetime) -> list[ReservationRecord]:
        """Return reservations whose time range overlaps the provided range."""
        ...

    def find_reservations(
        self,
        *,
        phone: str,
        reservation_start: datetime,
        customer_name: str | None = None,
        include_cancelled: bool = False,
    ) -> list[ReservationRecord]:
        """Find reservations by caller phone and start time."""
        ...


class InMemoryCalendarService:
    """Simple calendar fake for local development and unit tests."""

    def __init__(self) -> None:
        self.records: list[ReservationRecord] = []

    def create_reservation(self, record: ReservationRecord) -> ReservationRecord:
        self.records.append(record)
        return record

    def update_reservation(self, record: ReservationRecord) -> ReservationRecord:
        for index, existing in enumerate(self.records):
            if existing.id == record.id:
                self.records[index] = record
                return record
        raise ValueError(f"reservation record not found: {record.id}")

    def list_reservations(self, *, start: datetime, end: datetime) -> list[ReservationRecord]:
        requested_start = normalize_to_seoul(start)
        requested_end = normalize_to_seoul(end)
        return [
            record
            for record in self.records
            if reservations_overlap(record.start, record.end, requested_start, requested_end)
        ]

    def find_reservations(
        self,
        *,
        phone: str,
        reservation_start: datetime,
        customer_name: str | None = None,
        include_cancelled: bool = False,
    ) -> list[ReservationRecord]:
        normalized_start = normalize_to_seoul(reservation_start)
        matches = [
            record
            for record in self.records
            if record.phone == phone
            and record.start == normalized_start
            and (include_cancelled or record.status != CANCELLED_STATUS)
        ]
        if customer_name is not None:
            matches = [record for record in matches if record.customer_name == customer_name]
        return matches


class GoogleCalendarService:
    """Google Calendar-backed reservation storage implementation."""

    def __init__(self, *, events: Any, calendar_id: str) -> None:
        self._events = events
        self._calendar_id = calendar_id

    def create_reservation(self, record: ReservationRecord) -> ReservationRecord:
        body = self._event_body(record)
        response = self._events.insert(calendarId=self._calendar_id, body=body).execute()
        if isinstance(response, dict) and response.get("id"):
            record.id = str(response["id"])
        return record

    def update_reservation(self, record: ReservationRecord) -> ReservationRecord:
        if not record.id:
            raise ValueError("Google Calendar updates require an existing event id")

        self._events.patch(
            calendarId=self._calendar_id,
            eventId=record.id,
            body=self._event_body(record),
        ).execute()
        return record

    def list_reservations(self, *, start: datetime, end: datetime) -> list[ReservationRecord]:
        requested_start = normalize_to_seoul(start)
        requested_end = normalize_to_seoul(end)
        response = self._events.list(
            calendarId=self._calendar_id,
            timeMin=requested_start.isoformat(),
            timeMax=requested_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            showDeleted=False,
        ).execute()

        items = response.get("items", []) if isinstance(response, dict) else []
        records = [record for item in items if (record := self._record_from_event(item)) is not None]
        return [
            record
            for record in records
            if record.status != CANCELLED_STATUS
            and reservations_overlap(record.start, record.end, requested_start, requested_end)
        ]

    def find_reservations(
        self,
        *,
        phone: str,
        reservation_start: datetime,
        customer_name: str | None = None,
        include_cancelled: bool = False,
    ) -> list[ReservationRecord]:
        normalized_start = normalize_to_seoul(reservation_start)
        records = self._list_reservations_including_cancelled(
            start=normalized_start,
            end=normalized_start + timedelta(minutes=1),
        )
        matches = [
            record
            for record in records
            if record.phone == phone
            and record.start == normalized_start
            and (include_cancelled or record.status != CANCELLED_STATUS)
        ]
        if customer_name is not None:
            matches = [record for record in matches if record.customer_name == customer_name]
        return matches

    def _list_reservations_including_cancelled(
        self,
        *,
        start: datetime,
        end: datetime,
    ) -> list[ReservationRecord]:
        requested_start = normalize_to_seoul(start)
        requested_end = normalize_to_seoul(end)
        response = self._events.list(
            calendarId=self._calendar_id,
            timeMin=requested_start.isoformat(),
            timeMax=requested_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            showDeleted=False,
        ).execute()
        items = response.get("items", []) if isinstance(response, dict) else []
        return [
            record
            for item in items
            if (record := self._record_from_event(item)) is not None
            and reservations_overlap(record.start, record.end, requested_start, requested_end)
        ]

    def _event_body(self, record: ReservationRecord) -> dict[str, object]:
        record.start = normalize_to_seoul(record.start)
        record.end = normalize_to_seoul(record.end)
        return {
            "summary": f"{record.party_size} guests - {record.customer_name}",
            "description": self._event_description(record),
            "start": {
                "dateTime": record.start.isoformat(),
                "timeZone": "Asia/Seoul",
            },
            "end": {
                "dateTime": record.end.isoformat(),
                "timeZone": "Asia/Seoul",
            },
            "extendedProperties": {
                "private": self._private_metadata(record),
            },
        }

    def _event_description(self, record: ReservationRecord) -> str:
        lines = [
            f"Customer: {record.customer_name}",
            f"Phone: {record.phone}",
            f"Party size: {record.party_size}",
            f"Reservation start: {record.start.isoformat()}",
            f"Reservation end: {record.end.isoformat()}",
            f"Seating preference: {record.seating_preference.value}",
            f"Internal resource: {', '.join(record.resource_ids)}",
            f"Booking status: {record.status}",
        ]
        if record.private_room_minimum_spend_krw is not None:
            lines.append(
                f"Private-room minimum spend: {record.private_room_minimum_spend_krw} KRW"
            )
        if record.notes:
            lines.append(f"Notes: {record.notes}")
        if record.allergy_notes:
            lines.append(f"Allergy notes: {record.allergy_notes}")
        if record.call_id:
            lines.append(f"Vapi call ID: {record.call_id}")
        return "\n".join(lines)

    def _private_metadata(self, record: ReservationRecord) -> dict[str, str]:
        return {
            "customer_name": record.customer_name,
            "phone": record.phone,
            "party_size": str(record.party_size),
            "seating_preference": record.seating_preference.value,
            "resource_ids": ",".join(record.resource_ids),
            "notes": record.notes or "",
            "allergy_notes": record.allergy_notes or "",
            "call_id": record.call_id or "",
            "private_room_minimum_spend_krw": (
                str(record.private_room_minimum_spend_krw)
                if record.private_room_minimum_spend_krw is not None
                else ""
            ),
            "booking_status": record.status,
        }

    def _record_from_event(self, event: object) -> ReservationRecord | None:
        if not isinstance(event, dict):
            return None

        private = event.get("extendedProperties", {})
        if isinstance(private, dict):
            private = private.get("private", {})
        if not isinstance(private, dict):
            return None

        start = self._parse_event_datetime(event.get("start"))
        end = self._parse_event_datetime(event.get("end"))
        if start is None or end is None:
            return None

        resource_ids = tuple(
            resource_id
            for resource_id in str(private.get("resource_ids", "")).split(",")
            if resource_id
        )
        minimum_spend = self._optional_int(private.get("private_room_minimum_spend_krw"))

        return ReservationRecord(
            id=str(event.get("id", "")),
            customer_name=str(private.get("customer_name", "")),
            phone=str(private.get("phone", "")),
            party_size=int(private.get("party_size", 0)),
            start=start,
            end=end,
            seating_preference=SeatingPreference(str(private.get("seating_preference"))),
            resource_ids=resource_ids,
            notes=self._optional_string(private.get("notes")),
            allergy_notes=self._optional_string(private.get("allergy_notes")),
            call_id=self._optional_string(private.get("call_id")),
            private_room_minimum_spend_krw=minimum_spend,
            status=str(private.get("booking_status", CONFIRMED_STATUS)),
        )

    def _parse_event_datetime(self, value: object) -> datetime | None:
        if not isinstance(value, dict):
            return None
        date_time = value.get("dateTime")
        if not isinstance(date_time, str):
            return None
        return normalize_to_seoul(datetime.fromisoformat(date_time))

    def _optional_int(self, value: object) -> int | None:
        if value in (None, ""):
            return None
        return int(value)

    def _optional_string(self, value: object) -> str | None:
        if value in (None, ""):
            return None
        return str(value)


def build_google_calendar_service(settings: Settings) -> GoogleCalendarService:
    """Build a Google Calendar storage service from application settings."""
    if not settings.google_calendar_id:
        raise ValueError("GOOGLE_CALENDAR_ID is required for Google Calendar")

    scopes = [GOOGLE_CALENDAR_EVENTS_SCOPE]
    if settings.google_application_credentials:
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_application_credentials,
            scopes=scopes,
        )
    elif settings.google_service_account_json:
        service_account_info = json.loads(settings.google_service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=scopes,
        )
    else:
        raise ValueError(
            "GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_SERVICE_ACCOUNT_JSON is required "
            "for Google Calendar"
        )

    api = google_discovery.build("calendar", "v3", credentials=credentials)
    return GoogleCalendarService(events=api.events(), calendar_id=settings.google_calendar_id)
