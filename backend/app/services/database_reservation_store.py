"""SQLAlchemy-backed reservation storage implementation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.core.config import Settings
from app.db.models import (
    CustomerModel,
    ReservationModel,
    ReservationResourceAssignment,
)
from app.db.seed import seed_restaurant_resources
from app.db.session import Base, get_engine, get_session_factory
from app.models.resources import SeatingPreference
from app.services.resource_allocator import reservations_overlap
from app.services.reservation_store import CANCELLED_STATUS, ReservationRecord, ReservationStore
from app.utils.time import normalize_to_seoul


class SQLAlchemyReservationStore(ReservationStore):
    """Persist reservation records through SQLAlchemy sessions."""

    def __init__(self, *, session_factory: sessionmaker | Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create_reservation(self, record: ReservationRecord) -> ReservationRecord:
        record.start = normalize_to_seoul(record.start)
        record.end = normalize_to_seoul(record.end)
        with self._session_factory() as session:
            with session.begin():
                customer = self._get_or_create_customer(session, record)
                reservation = ReservationModel(
                    id=record.id,
                    customer_id=customer.id if customer is not None else None,
                    customer_name=record.customer_name,
                    phone=record.phone,
                    party_size=record.party_size,
                    start_at=record.start,
                    end_at=record.end,
                    seating_preference=record.seating_preference.value,
                    notes=record.notes,
                    allergy_notes=record.allergy_notes,
                    call_id=record.call_id,
                    private_room_minimum_spend_krw=record.private_room_minimum_spend_krw,
                    status=record.status,
                    source=record.source,
                    version=record.version,
                )
                session.add(reservation)
                self._replace_assignments(session, reservation_id=record.id, resource_ids=record.resource_ids)
            return self._record_from_model(reservation)

    def update_reservation(self, record: ReservationRecord) -> ReservationRecord:
        record.start = normalize_to_seoul(record.start)
        record.end = normalize_to_seoul(record.end)
        with self._session_factory() as session:
            with session.begin():
                reservation = session.get(ReservationModel, record.id)
                if reservation is None:
                    raise ValueError(f"reservation record not found: {record.id}")

                customer = self._get_or_create_customer(session, record)
                reservation.customer_id = customer.id if customer is not None else None
                reservation.customer_name = record.customer_name
                reservation.phone = record.phone
                reservation.party_size = record.party_size
                reservation.start_at = record.start
                reservation.end_at = record.end
                reservation.seating_preference = record.seating_preference.value
                reservation.notes = record.notes
                reservation.allergy_notes = record.allergy_notes
                reservation.call_id = record.call_id
                reservation.private_room_minimum_spend_krw = record.private_room_minimum_spend_krw
                reservation.status = record.status
                reservation.source = record.source
                reservation.version += 1
                self._replace_assignments(
                    session,
                    reservation_id=record.id,
                    resource_ids=record.resource_ids,
                )
            return self._record_from_model(reservation)

    def list_reservations(self, *, start: datetime, end: datetime) -> list[ReservationRecord]:
        requested_start = normalize_to_seoul(start)
        requested_end = normalize_to_seoul(end)
        with self._session_factory() as session:
            reservations = session.scalars(
                select(ReservationModel)
                .options(joinedload(ReservationModel.resource_assignments))
                .where(
                    ReservationModel.start_at < requested_end,
                    ReservationModel.end_at > requested_start,
                )
                .order_by(ReservationModel.start_at, ReservationModel.id)
            ).unique()
            return [
                self._record_from_model(reservation)
                for reservation in reservations
                if reservations_overlap(
                    normalize_to_seoul(reservation.start_at),
                    normalize_to_seoul(reservation.end_at),
                    requested_start,
                    requested_end,
                )
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
        search_end = normalized_start + timedelta(minutes=1)
        with self._session_factory() as session:
            reservations = session.scalars(
                select(ReservationModel)
                .options(joinedload(ReservationModel.resource_assignments))
                .where(
                    ReservationModel.phone == phone,
                    ReservationModel.start_at < search_end,
                    ReservationModel.end_at > normalized_start,
                )
                .order_by(ReservationModel.start_at, ReservationModel.id)
            ).unique()
            matches = [
                self._record_from_model(reservation)
                for reservation in reservations
                if normalize_to_seoul(reservation.start_at) == normalized_start
                and (include_cancelled or reservation.status != CANCELLED_STATUS)
            ]

        if customer_name is not None:
            matches = [record for record in matches if record.customer_name == customer_name]
        return matches

    def _get_or_create_customer(
        self,
        session: Session,
        record: ReservationRecord,
    ) -> CustomerModel | None:
        if not record.customer_name or not record.phone:
            return None

        customer = session.scalars(
            select(CustomerModel).where(
                CustomerModel.phone == record.phone,
                CustomerModel.name == record.customer_name,
            )
        ).first()
        if customer is not None:
            if record.allergy_notes:
                customer.allergies = record.allergy_notes
            return customer

        customer = CustomerModel(
            name=record.customer_name,
            phone=record.phone,
            allergies=record.allergy_notes,
        )
        session.add(customer)
        session.flush()
        return customer

    def _replace_assignments(
        self,
        session: Session,
        *,
        reservation_id: str,
        resource_ids: tuple[str, ...],
    ) -> None:
        session.execute(
            delete(ReservationResourceAssignment).where(
                ReservationResourceAssignment.reservation_id == reservation_id
            )
        )
        for resource_id in resource_ids:
            session.add(
                ReservationResourceAssignment(
                    reservation_id=reservation_id,
                    resource_id=resource_id,
                )
            )

    def _record_from_model(self, reservation: ReservationModel) -> ReservationRecord:
        resource_ids = tuple(
            assignment.resource_id
            for assignment in sorted(
                reservation.resource_assignments,
                key=lambda assignment: assignment.id,
            )
        )
        return ReservationRecord(
            id=reservation.id,
            customer_name=reservation.customer_name,
            phone=reservation.phone,
            party_size=reservation.party_size,
            start=normalize_to_seoul(reservation.start_at),
            end=normalize_to_seoul(reservation.end_at),
            seating_preference=SeatingPreference(reservation.seating_preference),
            resource_ids=resource_ids,
            notes=reservation.notes,
            allergy_notes=reservation.allergy_notes,
            call_id=reservation.call_id,
            private_room_minimum_spend_krw=reservation.private_room_minimum_spend_krw,
            status=reservation.status,
            source=reservation.source,
            version=reservation.version,
        )


def build_database_reservation_store(settings: Settings) -> SQLAlchemyReservationStore:
    """Build the database-backed reservation store from application settings."""
    if not settings.database_url:
        raise ValueError("DATABASE_URL is required for database-backed reservations")

    engine = get_engine(settings.database_url)
    session_factory = get_session_factory(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            seed_restaurant_resources(session)

    return SQLAlchemyReservationStore(session_factory=session_factory)
