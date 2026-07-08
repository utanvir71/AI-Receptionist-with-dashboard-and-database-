"""Storage-neutral reservation persistence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from app.models.resources import SeatingPreference
from app.services.resource_allocator import reservations_overlap
from app.utils.time import normalize_to_seoul


CONFIRMED_STATUS = "confirmed"
CANCELLED_STATUS = "cancelled"


@dataclass
class ReservationRecord:
    """Internal reservation record used by storage implementations."""

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
    source: str = "ai_call"
    version: int = 1
    id: str = ""

    def __post_init__(self) -> None:
        self.start = normalize_to_seoul(self.start)
        self.end = normalize_to_seoul(self.end)
        if not self.id:
            self.id = uuid4().hex


class ReservationStore(Protocol):
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


class InMemoryReservationStore:
    """Simple reservation store fake for local development and unit tests."""

    def __init__(self) -> None:
        self.records: list[ReservationRecord] = []

    def create_reservation(self, record: ReservationRecord) -> ReservationRecord:
        self.records.append(record)
        return record

    def update_reservation(self, record: ReservationRecord) -> ReservationRecord:
        for index, existing in enumerate(self.records):
            if existing.id == record.id:
                record.version = existing.version + 1
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
