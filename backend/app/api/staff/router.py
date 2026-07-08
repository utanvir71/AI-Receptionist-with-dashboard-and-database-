"""Staff dashboard API routes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.core.config import Settings, get_settings
from app.core.staff_auth import (
    create_staff_session_token,
    verify_staff_password,
    verify_staff_session_token,
)
from app.db.seed import seed_restaurant_resources
from app.db.session import Base, get_engine, get_session_factory
from app.schemas.staff import (
    BackupResponse,
    CallLogListResponse,
    CustomerDetailResponse,
    CustomerListResponse,
    DemoResetResponse,
    FloorResponse,
    FollowupListResponse,
    FollowupResponse,
    ReportResponse,
    ReservationListResponse,
    ReservationResponse,
    StaffCompleteRequest,
    StaffFollowupUpdateRequest,
    StaffLoginRequest,
    StaffLoginResponse,
    StaffReservationCreateRequest,
    StaffReservationPatchRequest,
    StaffVersionRequest,
    StaffWalkInCreateRequest,
)
from app.services.notification_service import build_reservation_notifier
from app.services.staff_service import (
    StaffConflictError,
    StaffEvent,
    StaffEventHub,
    StaffNotFoundError,
    StaffService,
    StaffValidationError,
)
from app.utils.time import SEOUL_TZ


router = APIRouter()

_staff_event_hub: StaffEventHub | None = None
_staff_service: StaffService | None = None
_staff_service_signature: tuple[str, str, str, str, str] | None = None


def get_staff_event_hub() -> StaffEventHub:
    """Return the process-local staff event hub."""
    global _staff_event_hub
    if _staff_event_hub is None:
        _staff_event_hub = StaffEventHub()
    return _staff_event_hub


def get_staff_service(
    settings: Annotated[Settings, Depends(get_settings)],
    event_hub: Annotated[StaffEventHub, Depends(get_staff_event_hub)],
) -> StaffService:
    """Return the database-backed staff service."""
    global _staff_service, _staff_service_signature

    if not settings.database_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is required for staff dashboard APIs",
        )

    signature = (
        settings.database_url,
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_from_number,
        settings.backup_dir,
    )
    if _staff_service is not None and _staff_service_signature == signature:
        return _staff_service

    engine = get_engine(settings.database_url)
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
        from sqlalchemy.orm import Session

        with Session(engine) as session:
            seed_restaurant_resources(session)

    _staff_service = StaffService(
        session_factory=get_session_factory(settings.database_url),
        notifier=build_reservation_notifier(settings),
        event_hub=event_hub,
        backup_dir=Path(settings.backup_dir),
    )
    _staff_service_signature = signature
    return _staff_service


def require_staff_session(
    staff_session: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    """Require a signed staff session token from cookie or bearer auth."""
    if not settings.session_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="staff session secret is not configured",
        )

    token = staff_session
    scheme, _, bearer_token = (authorization or "").partition(" ")
    if token is None and scheme == "Bearer":
        token = bearer_token

    if token is None or not verify_staff_session_token(token, settings.session_secret_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid staff session",
        )


RequireStaffAuth = Annotated[None, Depends(require_staff_session)]


@router.post("/auth/login", response_model=StaffLoginResponse)
def login(
    request: StaffLoginRequest,
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> StaffLoginResponse:
    """Create a shared staff session when the password matches."""
    if not settings.staff_password_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="staff password hash is not configured",
        )
    if not settings.session_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="staff session secret is not configured",
        )
    if not verify_staff_password(request.password, settings.staff_password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid staff password",
        )

    token = create_staff_session_token(settings.session_secret_key)
    response.set_cookie(
        "staff_session",
        token,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return StaffLoginResponse(authenticated=True)


@router.get("/floor", response_model=FloorResponse)
def floor_state(
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
    date: date,
    time: time,
) -> dict[str, Any]:
    """Return floor state for a selected date and time."""
    return service.floor_state(selected_date=date, selected_time=time)


@router.get("/reservations", response_model=ReservationListResponse)
def list_reservations(
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
    status: str | None = None,
    q: str | None = None,
    date: date | None = None,
) -> dict[str, Any]:
    """List/search staff reservations."""
    return {"items": service.list_reservations(status=status, query=q, day=date)}


@router.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation(
    request: StaffReservationCreateRequest,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Create a staff reservation."""
    response, event = _call_staff_service(lambda: service.create_reservation(request))
    await _broadcast(service, event)
    return response


@router.get("/reservations/{reservation_id}", response_model=ReservationResponse)
def get_reservation(
    reservation_id: str,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Return one reservation."""
    return _call_staff_service(lambda: service.get_reservation(reservation_id))


@router.patch("/reservations/{reservation_id}", response_model=ReservationResponse)
async def patch_reservation(
    reservation_id: str,
    request: StaffReservationPatchRequest,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Edit a reservation."""
    response, event, _ = _call_staff_service(lambda: service.patch_reservation(reservation_id, request))
    await _broadcast(service, event)
    return response


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationResponse)
async def cancel_reservation(
    reservation_id: str,
    request: StaffVersionRequest,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Cancel a reservation."""
    response, event = _call_staff_service(lambda: service.cancel_reservation(reservation_id, request))
    await _broadcast(service, event)
    return response


@router.post("/reservations/{reservation_id}/arrive", response_model=ReservationResponse)
async def mark_arrived(
    reservation_id: str,
    request: StaffVersionRequest,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Mark a reservation as seated."""
    response, event = _call_staff_service(lambda: service.mark_arrived(reservation_id, request))
    await _broadcast(service, event)
    return response


@router.post("/reservations/{reservation_id}/complete", response_model=ReservationResponse)
async def complete_reservation(
    reservation_id: str,
    request: StaffCompleteRequest,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Complete a reservation or walk-in."""
    response, event = _call_staff_service(lambda: service.complete_reservation(reservation_id, request))
    await _broadcast(service, event)
    return response


@router.post("/reservations/{reservation_id}/no-show", response_model=ReservationResponse)
async def mark_no_show(
    reservation_id: str,
    request: StaffVersionRequest,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Mark a reservation as no-show."""
    response, event = _call_staff_service(lambda: service.mark_no_show(reservation_id, request))
    await _broadcast(service, event)
    return response


@router.post(
    "/walk-ins",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_walk_in(
    request: StaffWalkInCreateRequest,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Seat a walk-in."""
    response, event = _call_staff_service(lambda: service.create_walk_in(request))
    await _broadcast(service, event)
    return response


@router.get("/customers", response_model=CustomerListResponse)
def list_customers(
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
    q: str | None = None,
) -> dict[str, Any]:
    """Search customers."""
    return {"items": service.list_customers(query=q)}


@router.get("/customers/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(
    customer_id: str,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Return a customer profile."""
    return _call_staff_service(lambda: service.get_customer(customer_id))


@router.get("/follow-ups", response_model=FollowupListResponse)
def list_followups(
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
    status: str | None = None,
) -> dict[str, Any]:
    """List manager follow-ups."""
    return {"items": service.list_followups(status=status)}


@router.patch("/follow-ups/{followup_id}", response_model=FollowupResponse)
async def update_followup(
    followup_id: str,
    request: StaffFollowupUpdateRequest,
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Update a manager follow-up."""
    response, event = _call_staff_service(lambda: service.update_followup(followup_id, request))
    await _broadcast(service, event)
    return response


@router.get("/call-logs", response_model=CallLogListResponse)
def list_call_logs(
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """List Vapi call logs."""
    return {"items": service.list_call_logs()}


@router.get("/reports", response_model=ReportResponse)
def reports(
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
    range: str,
    date: date,
) -> dict[str, Any]:
    """Return dashboard report aggregates."""
    return _call_staff_service(lambda: service.report(report_range=range, start_date=date))


@router.post("/demo/reset", response_model=DemoResetResponse)
async def reset_demo(
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Reset fictional demo data when demo mode is enabled."""
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="demo reset is disabled",
        )
    response = _call_staff_service(service.reset_demo_data)
    await _broadcast(
        service,
        StaffEvent(
            type="demo.reset",
            entity="demo_data",
            id="demo",
            version=1,
            occurred_at=datetime.now(SEOUL_TZ),
        ),
    )
    return response


@router.post(
    "/backups",
    response_model=BackupResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_backup(
    _: RequireStaffAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Create a manual backup."""
    return _call_staff_service(service.create_backup)


@router.websocket("/ws")
async def staff_websocket(
    websocket: WebSocket,
    settings: Annotated[Settings, Depends(get_settings)],
    event_hub: Annotated[StaffEventHub, Depends(get_staff_event_hub)],
) -> None:
    """Staff live-update WebSocket."""
    token = websocket.cookies.get("staff_session")
    authorization = websocket.headers.get("authorization")
    scheme, _, bearer_token = (authorization or "").partition(" ")
    if token is None and scheme == "Bearer":
        token = bearer_token
    if not settings.session_secret_key or token is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not verify_staff_session_token(token, settings.session_secret_key):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await event_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_hub.disconnect(websocket)


async def _broadcast(service: StaffService, event: StaffEvent | None) -> None:
    if event is not None:
        await service.event_hub.broadcast(event)


def _call_staff_service(func: Callable[[], Any]) -> Any:
    try:
        return func()
    except StaffNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StaffConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StaffValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
