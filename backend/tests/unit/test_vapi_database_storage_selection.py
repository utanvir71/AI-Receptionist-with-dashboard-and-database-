"""Vapi service storage selection after database cutover."""

from app.api.v1 import vapi_tools
from app.api.v1.vapi_tools import get_reservation_service
from app.core.config import Settings
from app.services.database_reservation_store import SQLAlchemyReservationStore
from app.services.reservation_service import ReservationService


def test_vapi_service_uses_database_store_when_database_url_is_configured() -> None:
    vapi_tools._reservation_service = None
    vapi_tools._reservation_service_signature = None

    service = get_reservation_service(
        Settings(
            database_url="sqlite+pysqlite:///:memory:",
            google_calendar_id="legacy-calendar-id",
        )
    )

    assert isinstance(service, ReservationService)
    assert isinstance(service.calendar, SQLAlchemyReservationStore)
