"""Reservation service behavior with the SQLAlchemy storage backend."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import seed_restaurant_resources
from app.db.session import Base
from app.models.resources import SeatingPreference
from app.schemas.reservations import (
    CancelReservationRequest,
    CreateReservationRequest,
    ModifyReservationRequest,
    SearchReservationRequest,
    VapiToolStatus,
)
from app.services.database_reservation_store import SQLAlchemyReservationStore
from app.services.reservation_service import ReservationService
from app.utils.time import SEOUL_TZ


NOW = datetime(2026, 6, 25, 10, 0, tzinfo=SEOUL_TZ)


def seoul_datetime(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SEOUL_TZ)


def database_service() -> ReservationService:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as session:
        seed_restaurant_resources(session)
    return ReservationService(
        calendar=SQLAlchemyReservationStore(session_factory=session_factory),
        now_provider=lambda: NOW,
    )


def create_request(
    *,
    party_size: int = 4,
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
        notes="birthday",
        allergy_notes="peanut allergy",
        call_id="call-123",
    )


def test_reservation_service_create_search_modify_cancel_with_database_store() -> None:
    service = database_service()

    created = service.create_reservation(create_request())
    assert created.status == VapiToolStatus.CONFIRMED

    found = service.search_reservation(
        SearchReservationRequest(
            phone="+821012345678",
            reservation_start=seoul_datetime(2026, 7, 1, 18),
        )
    )
    assert found.status == VapiToolStatus.CONFIRMED
    assert found.data["customer_name"] == "Jane Kim"

    modified = service.modify_reservation(
        ModifyReservationRequest(
            phone="+821012345678",
            original_reservation_start=seoul_datetime(2026, 7, 1, 18),
            new_reservation_start=seoul_datetime(2026, 7, 1, 19),
            new_party_size=5,
        )
    )
    assert modified.status == VapiToolStatus.CONFIRMED
    assert modified.data["reservation_start"] == "2026-07-01T19:00:00+09:00"
    assert modified.data["party_size"] == 5

    cancelled = service.cancel_reservation(
        CancelReservationRequest(
            phone="+821012345678",
            reservation_start=seoul_datetime(2026, 7, 1, 19),
        )
    )
    assert cancelled.status == VapiToolStatus.CANCELLED

    replacement = service.create_reservation(
        create_request(
            reservation_start=seoul_datetime(2026, 7, 1, 19),
            phone="+821099999999",
            name="Replacement Guest",
        )
    )
    assert replacement.status == VapiToolStatus.CONFIRMED
