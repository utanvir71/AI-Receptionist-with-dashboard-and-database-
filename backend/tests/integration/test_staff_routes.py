"""Staff dashboard API behavior."""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.staff.router import get_staff_event_hub, get_staff_service
from app.api.v1.vapi_tools import _response_cache
from app.core.config import Settings, get_settings
from app.core.staff_auth import hash_staff_password
from app.db.models import AuditLogModel, ManagerFollowupModel, ReservationModel
from app.db.seed import seed_restaurant_resources
from app.db.session import Base
from app.main import app
from app.services.reservation_store import ReservationRecord
from app.services.staff_service import StaffEventHub, StaffService
from app.utils.time import SEOUL_TZ


NOW = datetime(2026, 7, 1, 17, 0, tzinfo=SEOUL_TZ)


class RecordingReservationNotifier:
    """Fake notifier that records SMS decisions without external calls."""

    def __init__(self) -> None:
        self.confirmations: list[str] = []
        self.modifications: list[str] = []
        self.cancellations: list[str] = []

    def send_confirmation(self, record: ReservationRecord) -> None:
        self.confirmations.append(record.id)

    def send_modification(self, record: ReservationRecord) -> None:
        self.modifications.append(record.id)

    def send_cancellation(self, record: ReservationRecord) -> None:
        self.cancellations.append(record.id)


@pytest.fixture
def staff_client(
    tmp_path: Path,
) -> Generator[tuple[TestClient, RecordingReservationNotifier, StaffService]]:
    _response_cache.clear()
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with Session(engine) as session:
        seed_restaurant_resources(session)
        session.add(
            ManagerFollowupModel(
                id="followup-1",
                customer_name="Jane Kim",
                phone="+821012345678",
                reason="party size over 12",
                status="open",
            )
        )
        session.commit()

    notifier = RecordingReservationNotifier()
    event_hub = StaffEventHub()
    service = StaffService(
        session_factory=session_factory,
        notifier=notifier,
        event_hub=event_hub,
        now_provider=lambda: NOW,
        backup_dir=tmp_path,
    )
    settings = Settings(
        vapi_tool_secret="vapi-secret",
        staff_password_hash=hash_staff_password("open-sesame", salt="testsalt"),
        session_secret_key="test-session-secret",
        demo_mode=True,
        backup_dir=str(tmp_path),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_staff_service] = lambda: service
    app.dependency_overrides[get_staff_event_hub] = lambda: event_hub
    try:
        yield TestClient(app), notifier, service
    finally:
        app.dependency_overrides.clear()


def login(client: TestClient) -> None:
    response = client.post("/api/staff/auth/login", json={"password": "open-sesame"})

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert "staff_session" in response.cookies


def test_staff_auth_uses_shared_password_and_rejects_vapi_bearer(
    staff_client: tuple[TestClient, RecordingReservationNotifier, StaffService],
) -> None:
    client, _, _ = staff_client

    unauthenticated = client.get("/api/staff/reservations")
    assert unauthenticated.status_code == 401

    wrong_password = client.post("/api/staff/auth/login", json={"password": "wrong"})
    assert wrong_password.status_code == 401

    bearer_only = client.get(
        "/api/staff/reservations",
        headers={"Authorization": "Bearer vapi-secret"},
    )
    assert bearer_only.status_code == 401

    login(client)
    authenticated = client.get("/api/staff/reservations")
    assert authenticated.status_code == 200


def test_staff_reservation_lifecycle_sms_and_stale_version_conflict(
    staff_client: tuple[TestClient, RecordingReservationNotifier, StaffService],
) -> None:
    client, notifier, _ = staff_client
    login(client)

    created_response = client.post(
        "/api/staff/reservations",
        json={
            "customer_name": "Jane Kim",
            "phone": "+821012345678",
            "party_size": 4,
            "reservation_start": "2026-07-01T18:00:00+09:00",
            "seating_preference": "no_preference",
            "resource_id": "table_3",
            "notes": "window if possible",
            "allergy_notes": "peanut allergy",
        },
    )

    assert created_response.status_code == 201
    created = created_response.json()
    assert created["status"] == "confirmed"
    assert created["source"] == "staff_manual"
    assert created["resource_ids"] == ["table_3"]
    assert created["version"] == 1
    assert notifier.confirmations == [created["id"]]

    moved_response = client.patch(
        f"/api/staff/reservations/{created['id']}",
        json={"expected_version": 1, "resource_id": "table_4"},
    )

    assert moved_response.status_code == 200
    moved = moved_response.json()
    assert moved["resource_ids"] == ["table_4"]
    assert moved["version"] == 2
    assert notifier.modifications == []

    stale_response = client.patch(
        f"/api/staff/reservations/{created['id']}",
        json={"expected_version": 1, "notes": "stale edit"},
    )
    assert stale_response.status_code == 409
    assert stale_response.json()["detail"] == "record changed, reload before saving"

    changed_time_response = client.patch(
        f"/api/staff/reservations/{created['id']}",
        json={"expected_version": 2, "reservation_start": "2026-07-01T19:00:00+09:00"},
    )

    assert changed_time_response.status_code == 200
    changed_time = changed_time_response.json()
    assert changed_time["reservation_start"] == "2026-07-01T19:00:00+09:00"
    assert changed_time["version"] == 3
    assert notifier.modifications == [created["id"]]

    arrived_response = client.post(
        f"/api/staff/reservations/{created['id']}/arrive",
        json={"expected_version": 3},
    )
    assert arrived_response.status_code == 200
    assert arrived_response.json()["status"] == "seated"

    missing_bill_response = client.post(
        f"/api/staff/reservations/{created['id']}/complete",
        json={"expected_version": 4},
    )
    assert missing_bill_response.status_code == 422

    completed_response = client.post(
        f"/api/staff/reservations/{created['id']}/complete",
        json={"expected_version": 4, "final_bill_krw": 45000},
    )
    assert completed_response.status_code == 200
    completed = completed_response.json()
    assert completed["status"] == "completed"
    assert completed["final_bill_krw"] == 45000

    report_response = client.get("/api/staff/reports", params={"range": "daily", "date": "2026-07-01"})
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["metrics"]["bookings"] == 1
    assert report["metrics"]["completed_visits"] == 1
    assert report["metrics"]["revenue_krw"] == 45000

    audits_response = client.get("/api/staff/reservations", params={"status": "completed"})
    assert audits_response.status_code == 200
    assert audits_response.json()["items"][0]["status"] == "completed"


def test_staff_cancel_no_show_walk_in_and_floor_rules(
    staff_client: tuple[TestClient, RecordingReservationNotifier, StaffService],
) -> None:
    client, notifier, _ = staff_client
    login(client)

    future = client.post(
        "/api/staff/reservations",
        json={
            "customer_name": "Min Park",
            "phone": "+821011112222",
            "party_size": 2,
            "reservation_start": "2026-07-01T18:00:00+09:00",
            "seating_preference": "no_preference",
            "resource_id": "table_3",
        },
    ).json()

    blocked_walk_in = client.post(
        "/api/staff/walk-ins",
        json={"party_size": 2, "resource_id": "table_3"},
    )
    assert blocked_walk_in.status_code == 409
    assert "full 100-minute free window" in blocked_walk_in.json()["detail"]

    walk_in_response = client.post(
        "/api/staff/walk-ins",
        json={"party_size": 2, "resource_id": "table_4"},
    )
    assert walk_in_response.status_code == 201
    walk_in = walk_in_response.json()
    assert walk_in["source"] == "walk_in"
    assert walk_in["status"] == "seated"
    assert notifier.confirmations == [future["id"]]

    floor_response = client.get(
        "/api/staff/floor",
        params={"date": "2026-07-01", "time": "17:05"},
    )
    assert floor_response.status_code == 200
    table_4 = next(resource for resource in floor_response.json()["resources"] if resource["id"] == "table_4")
    assert table_4["status"] == "occupied"
    assert table_4["current_reservation"]["id"] == walk_in["id"]

    no_show_response = client.post(
        f"/api/staff/reservations/{future['id']}/no-show",
        json={"expected_version": future["version"]},
    )
    assert no_show_response.status_code == 200
    assert no_show_response.json()["status"] == "no_show"
    assert notifier.cancellations == []

    cancelled_reservation = client.post(
        "/api/staff/reservations",
        json={
            "customer_name": "Cancel Guest",
            "phone": "+821033334444",
            "party_size": 2,
            "reservation_start": "2026-07-01T19:00:00+09:00",
            "seating_preference": "no_preference",
            "resource_id": "table_5",
        },
    ).json()
    cancelled = client.post(
        f"/api/staff/reservations/{cancelled_reservation['id']}/cancel",
        json={"expected_version": cancelled_reservation["version"]},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert notifier.cancellations == [cancelled_reservation["id"]]

    cancelled_walk_in = client.post(
        f"/api/staff/reservations/{walk_in['id']}/cancel",
        json={"expected_version": walk_in["version"]},
    )
    assert cancelled_walk_in.status_code == 200
    assert cancelled_walk_in.json()["status"] == "cancelled"
    assert notifier.cancellations == [cancelled_reservation["id"]]


def test_staff_customers_followups_call_logs_demo_reset_backup_and_audit(
    staff_client: tuple[TestClient, RecordingReservationNotifier, StaffService],
) -> None:
    client, _, service = staff_client
    login(client)

    created = client.post(
        "/api/staff/reservations",
        json={
            "customer_name": "Jane Kim",
            "phone": "+821012345678",
            "party_size": 2,
            "reservation_start": "2026-07-01T18:30:00+09:00",
            "seating_preference": "private_room",
            "resource_id": "room_1",
            "allergy_notes": "shellfish",
        },
    ).json()

    customers_response = client.get("/api/staff/customers", params={"q": "Jane"})
    assert customers_response.status_code == 200
    customer = customers_response.json()["items"][0]
    assert customer["name"] == "Jane Kim"
    assert customer["total_visits"] == 0
    assert customer["upcoming_bookings"] == 1

    customer_detail_response = client.get(f"/api/staff/customers/{customer['id']}")
    assert customer_detail_response.status_code == 200
    assert customer_detail_response.json()["allergies"] == "shellfish"

    followups_response = client.get("/api/staff/follow-ups")
    assert followups_response.status_code == 200
    assert followups_response.json()["items"][0]["status"] == "open"

    resolved_response = client.patch(
        "/api/staff/follow-ups/followup-1",
        json={"status": "resolved", "notes": "manager called back"},
    )
    assert resolved_response.status_code == 200
    assert resolved_response.json()["status"] == "resolved"

    call_log_response = client.post(
        "/vapi/call-logs",
        headers={"Authorization": "Bearer vapi-secret"},
        json={
            "call_time": "2026-07-01T17:10:00+09:00",
            "customer_phone": "+821012345678",
            "summary": "Caller asked about room availability.",
            "action_taken": "reservation_created",
            "reservation_id": created["id"],
        },
    )
    assert call_log_response.status_code == 201

    call_logs_response = client.get("/api/staff/call-logs")
    assert call_logs_response.status_code == 200
    assert call_logs_response.json()["items"][0]["summary"] == "Caller asked about room availability."

    backup_response = client.post("/api/staff/backups")
    assert backup_response.status_code == 201
    assert backup_response.json()["status"] == "created"

    demo_reset_response = client.post("/api/staff/demo/reset")
    assert demo_reset_response.status_code == 200
    assert demo_reset_response.json()["reset"] is True

    with service._session_factory() as session:
        assert session.scalar(select(AuditLogModel).where(AuditLogModel.action == "demo_reset")) is not None
        assert session.scalar(select(ReservationModel).where(ReservationModel.id == created["id"])) is None


def test_staff_websocket_receives_committed_reservation_event(
    staff_client: tuple[TestClient, RecordingReservationNotifier, StaffService],
) -> None:
    client, _, _ = staff_client
    login(client)

    with client.websocket_connect("/api/staff/ws") as websocket:
        response = client.post(
            "/api/staff/reservations",
            json={
                "customer_name": "Live Guest",
                "phone": "+821099998888",
                "party_size": 3,
                "reservation_start": "2026-07-01T19:00:00+09:00",
                "seating_preference": "no_preference",
                "resource_id": "table_5",
            },
        )
        assert response.status_code == 201
        event = websocket.receive_json()

    assert event["type"] == "reservation.created"
    assert event["entity"] == "reservation"
    assert event["id"] == response.json()["id"]
    assert event["version"] == 1
