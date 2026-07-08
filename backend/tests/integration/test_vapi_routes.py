from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api.v1.vapi_tools import _response_cache, get_reservation_service
from app.core.config import Settings, get_settings
from app.main import app
from app.services.calendar_service import InMemoryCalendarService
from app.services.reservation_service import ReservationService
from app.utils.time import SEOUL_TZ


NOW = datetime(2026, 6, 25, 10, 0, tzinfo=SEOUL_TZ)


@pytest.fixture
def client() -> Generator[TestClient]:
    _response_cache.clear()
    calendar = InMemoryCalendarService()
    service = ReservationService(calendar=calendar, now_provider=lambda: NOW)
    app.dependency_overrides[get_settings] = lambda: Settings(vapi_tool_secret="test-secret")
    app.dependency_overrides[get_reservation_service] = lambda: service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-secret"}


def valid_create_payload() -> dict[str, object]:
    return {
        "customer_name": "Tanvir",
        "phone": "+821012345678",
        "party_size": 4,
        "reservation_start": "2026-07-01T18:10:00+09:00",
        "seating_preference": "no_preference",
        "notes": "quiet area",
        "call_id": "call_123",
    }


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        (
            "post",
            "/vapi/reservations/check-availability",
            {
                "party_size": 4,
                "reservation_start": "2026-06-25T18:10:00+09:00",
                "seating_preference": "window_side",
            },
        ),
        ("post", "/vapi/reservations/create", valid_create_payload()),
        (
            "post",
            "/vapi/reservations/search",
            {
                "phone": "+821012345678",
                "reservation_start": "2026-06-25T18:10:00+09:00",
            },
        ),
        (
            "post",
            "/vapi/reservations/modify",
            {
                "phone": "+821012345678",
                "original_reservation_start": "2026-06-25T18:10:00+09:00",
                "new_party_size": 5,
            },
        ),
        (
            "post",
            "/vapi/reservations/cancel",
            {
                "phone": "+821012345678",
                "reservation_start": "2026-06-25T18:10:00+09:00",
            },
        ),
        (
            "post",
            "/vapi/reservations/manager-followup",
            {
                "customer_name": "Tanvir",
                "phone": "+821012345678",
                "reason": "manager transfer failed",
            },
        ),
    ],
)
def test_vapi_routes_accept_valid_authenticated_payloads(
    client: TestClient,
    method: str,
    path: str,
    payload: dict[str, object],
) -> None:
    response = getattr(client, method)(path, json=payload, headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["status"] in {
        "available",
        "confirmed",
        "cancelled",
        "not_found",
        "accepted",
    }


def test_vapi_routes_reject_missing_authorization(client: TestClient) -> None:
    response = client.post("/vapi/reservations/create", json=valid_create_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid Vapi tool authorization"


def test_vapi_routes_reject_invalid_payload(client: TestClient) -> None:
    payload = valid_create_payload()
    payload["phone"] = "010-1234-5678"

    response = client.post("/vapi/reservations/create", json=payload, headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["status"] == "invalid_request"


def test_check_availability_route_returns_real_service_result(client: TestClient) -> None:
    response = client.post(
        "/vapi/reservations/check-availability",
        json={
            "party_size": 4,
            "reservation_start": "2026-07-01T18:10:00+09:00",
            "seating_preference": "window_side",
        },
        headers=auth_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["message"] == "That time is available."
    assert body["data"]["reservation_start"] == "2026-07-01T18:10:00+09:00"
    assert body["data"]["reservation_end"] == "2026-07-01T19:50:00+09:00"


def test_check_availability_accepts_vapi_wrapped_tool_call_body(client: TestClient) -> None:
    response = client.post(
        "/vapi/reservations/check-availability",
        json={
            "message": {
                "type": "tool-calls",
                "toolCall": {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "check_availability",
                        "arguments": {
                            "party_size": 4,
                            "reservation_start": "2026-07-01T18:10:00+09:00",
                            "seating_preference": "no_preference",
                        },
                    },
                },
            },
        },
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "toolCallId": "call_123",
                "result": {
                    "status": "available",
                    "message": "That time is available.",
                    "data": {
                        "reservation_start": "2026-07-01T18:10:00+09:00",
                        "reservation_end": "2026-07-01T19:50:00+09:00",
                    },
                },
            }
        ]
    }


def test_create_then_search_and_cancel_routes_share_reservation_service(client: TestClient) -> None:
    create_response = client.post(
        "/vapi/reservations/create",
        json=valid_create_payload(),
        headers=auth_headers(),
    )

    assert create_response.status_code == 200
    assert create_response.json()["status"] == "confirmed"

    search_response = client.post(
        "/vapi/reservations/search",
        json={
            "phone": "+821012345678",
            "reservation_start": "2026-07-01T18:10:00+09:00",
        },
        headers=auth_headers(),
    )

    assert search_response.status_code == 200
    assert search_response.json()["status"] == "confirmed"
    assert search_response.json()["data"]["customer_name"] == "Tanvir"

    cancel_response = client.post(
        "/vapi/reservations/cancel",
        json={
            "phone": "+821012345678",
            "reservation_start": "2026-07-01T18:10:00+09:00",
        },
        headers=auth_headers(),
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_create_route_reuses_response_for_duplicate_idempotency_key(client: TestClient) -> None:
    headers = {**auth_headers(), "Idempotency-Key": "vapi-call-123-create"}

    first_response = client.post(
        "/vapi/reservations/create",
        json=valid_create_payload(),
        headers=headers,
    )
    duplicate_response = client.post(
        "/vapi/reservations/create",
        json=valid_create_payload(),
        headers=headers,
    )

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 200
    assert first_response.json()["status"] == "confirmed"
    assert duplicate_response.json() == first_response.json()


def test_vapi_route_returns_caller_safe_error_when_service_fails() -> None:
    class FailingReservationService:
        def check_availability(self, request: object) -> None:
            raise RuntimeError("calendar credentials leaked details")

    app.dependency_overrides[get_settings] = lambda: Settings(vapi_tool_secret="test-secret")
    app.dependency_overrides[get_reservation_service] = lambda: FailingReservationService()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/vapi/reservations/check-availability",
            json={
                "party_size": 4,
                "reservation_start": "2026-07-01T18:10:00+09:00",
                "seating_preference": "window_side",
            },
            headers=auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "error",
        "message": "The reservation system had an error. Transfer the caller to a manager.",
        "data": {"next_action": "transfer_to_manager"},
    }


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
