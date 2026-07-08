"""SQLAlchemy-backed reservation storage behavior."""

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import seed_restaurant_resources
from app.db.session import Base
from app.models.resources import SeatingPreference
from app.services.database_reservation_store import SQLAlchemyReservationStore
from app.services.reservation_store import CANCELLED_STATUS, ReservationRecord
from app.utils.time import SEOUL_TZ


def seoul_datetime(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SEOUL_TZ)


def store() -> SQLAlchemyReservationStore:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as session:
        seed_restaurant_resources(session)
    return SQLAlchemyReservationStore(session_factory=session_factory)


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
    }
    values.update(overrides)
    return ReservationRecord(**values)


def test_create_list_find_update_and_cancelled_records_round_trip() -> None:
    reservation_store = store()

    created = reservation_store.create_reservation(reservation_record(id=""))

    assert created.id
    assert created.status == "confirmed"
    assert created.resource_ids == ("table_3",)

    listed = reservation_store.list_reservations(
        start=seoul_datetime(2026, 7, 1, 17),
        end=seoul_datetime(2026, 7, 1, 20),
    )
    assert [record.id for record in listed] == [created.id]
    assert listed[0].customer_name == "Jane Kim"
    assert listed[0].start.isoformat() == "2026-07-01T18:00:00+09:00"

    found = reservation_store.find_reservations(
        phone="+821012345678",
        reservation_start=seoul_datetime(2026, 7, 1, 18),
        customer_name="Jane Kim",
    )
    assert [record.id for record in found] == [created.id]

    created.status = CANCELLED_STATUS
    updated = reservation_store.update_reservation(created)
    assert updated.status == CANCELLED_STATUS

    active_matches = reservation_store.find_reservations(
        phone="+821012345678",
        reservation_start=seoul_datetime(2026, 7, 1, 18),
    )
    all_matches = reservation_store.find_reservations(
        phone="+821012345678",
        reservation_start=seoul_datetime(2026, 7, 1, 18),
        include_cancelled=True,
    )
    assert active_matches == []
    assert [record.id for record in all_matches] == [created.id]
