"""Vapi custom tool endpoints."""

from collections.abc import Callable
import logging
from dataclasses import dataclass
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Body, Depends, Header
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.security import require_vapi_authorization
from app.schemas.reservations import (
    CancelReservationRequest,
    CheckAvailabilityRequest,
    CreateReservationRequest,
    ManagerFollowupRequest,
    ModifyReservationRequest,
    SearchReservationRequest,
    VapiToolResponse,
    VapiToolStatus,
)
from app.services.calendar_service import InMemoryCalendarService, build_google_calendar_service
from app.services.notification_service import (
    build_manager_email_notifier,
    build_reservation_notifier,
)
from app.services.reservation_service import ReservationService
from app.utils.idempotency import IdempotencyCache


router = APIRouter()
logger = logging.getLogger(__name__)

RequireVapiAuth = Annotated[None, Depends(require_vapi_authorization)]
IdempotencyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]
TRequest = TypeVar("TRequest")
TModel = TypeVar("TModel")

_response_cache = IdempotencyCache[VapiToolResponse]()
_reservation_service: ReservationService | None = None
_reservation_service_signature: tuple[str, str, str, str, str, str] | None = None


@dataclass(frozen=True)
class ParsedToolBody:
    """Normalized request data from direct API calls or Vapi tool-call webhooks."""

    arguments: dict[str, Any]
    tool_call_id: str | None = None


def get_reservation_service(settings: Settings = Depends(get_settings)) -> ReservationService:
    """Return the process-local reservation service for Vapi route calls."""
    global _reservation_service, _reservation_service_signature

    signature = (
        settings.google_calendar_id,
        settings.google_service_account_json,
        settings.google_application_credentials,
        settings.twilio_account_sid,
        settings.twilio_auth_token,
        settings.twilio_from_number,
    )
    if _reservation_service is not None and _reservation_service_signature == signature:
        return _reservation_service

    if settings.google_calendar_id:
        calendar = build_google_calendar_service(settings)
    else:
        calendar = InMemoryCalendarService()

    _reservation_service = ReservationService(
        calendar=calendar,
        notifier=build_reservation_notifier(settings),
    )
    _reservation_service_signature = signature
    return _reservation_service


def _caller_safe_error() -> VapiToolResponse:
    return VapiToolResponse(
        status=VapiToolStatus.ERROR,
        message="The reservation system had an error. Transfer the caller to a manager.",
        data={"next_action": "transfer_to_manager"},
    )


def _invalid_request_response(exc: ValidationError) -> VapiToolResponse:
    return VapiToolResponse(
        status=VapiToolStatus.INVALID_REQUEST,
        message="The reservation request was missing required details or used an invalid format.",
        data={"errors": exc.errors(include_context=False)},
    )


def _parse_tool_body(body: dict[str, Any]) -> ParsedToolBody:
    """Return direct request JSON or Vapi's nested tool-call arguments."""
    message = body.get("message")
    if not isinstance(message, dict):
        return ParsedToolBody(arguments=body)

    tool_call = message.get("toolCall")
    if not isinstance(tool_call, dict):
        tool_calls = message.get("toolCalls") or message.get("toolCallList")
        if isinstance(tool_calls, list) and tool_calls and isinstance(tool_calls[0], dict):
            tool_call = tool_calls[0]

    function = tool_call.get("function") if isinstance(tool_call, dict) else None
    arguments = function.get("arguments") if isinstance(function, dict) else None
    if isinstance(arguments, dict):
        tool_call_id = tool_call.get("id")
        return ParsedToolBody(
            arguments=arguments,
            tool_call_id=tool_call_id if isinstance(tool_call_id, str) else None,
        )

    return ParsedToolBody(arguments=body)


def _validated_request(model: type[TModel], body: dict[str, Any]) -> TModel | VapiToolResponse:
    try:
        return model.model_validate(_parse_tool_body(body).arguments)
    except ValidationError as exc:
        return _invalid_request_response(exc)


def _format_tool_response(body: dict[str, Any], response: VapiToolResponse) -> dict[str, Any] | VapiToolResponse:
    parsed = _parse_tool_body(body)
    if parsed.tool_call_id is None:
        return response
    return {
        "results": [
            {
                "toolCallId": parsed.tool_call_id,
                "result": response.model_dump(mode="json"),
            }
        ]
    }


def _execute_tool(
    *,
    tool_name: str,
    request: TRequest,
    operation: Callable[[TRequest], VapiToolResponse],
    idempotency_key: str | None,
) -> VapiToolResponse:
    cache_key = (tool_name, idempotency_key)
    if idempotency_key:
        cached = _response_cache.get(cache_key)
        if cached is not None:
            return cached

    try:
        response = operation(request)
    except Exception:
        logger.exception("Vapi tool %s failed", tool_name)
        response = _caller_safe_error()

    if idempotency_key:
        _response_cache.set(cache_key, response)
    return response


@router.post("/check-availability")
def check_availability(
    body: Annotated[dict[str, Any], Body()],
    _: RequireVapiAuth,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    idempotency_key: IdempotencyHeader = None,
) -> dict[str, Any] | VapiToolResponse:
    """Check whether the requested reservation time can be booked."""
    request = _validated_request(CheckAvailabilityRequest, body)
    if isinstance(request, VapiToolResponse):
        return _format_tool_response(body, request)
    response = _execute_tool(
        tool_name="check_availability",
        request=request,
        operation=service.check_availability,
        idempotency_key=idempotency_key,
    )
    return _format_tool_response(body, response)


@router.post("/create")
def create_reservation(
    body: Annotated[dict[str, Any], Body()],
    _: RequireVapiAuth,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    idempotency_key: IdempotencyHeader = None,
) -> dict[str, Any] | VapiToolResponse:
    """Create a confirmed reservation when availability rules pass."""
    request = _validated_request(CreateReservationRequest, body)
    if isinstance(request, VapiToolResponse):
        return _format_tool_response(body, request)
    response = _execute_tool(
        tool_name="create_reservation",
        request=request,
        operation=service.create_reservation,
        idempotency_key=idempotency_key,
    )
    return _format_tool_response(body, response)


@router.post("/search")
def search_reservation(
    body: Annotated[dict[str, Any], Body()],
    _: RequireVapiAuth,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    idempotency_key: IdempotencyHeader = None,
) -> dict[str, Any] | VapiToolResponse:
    """Search for an active reservation by phone and reservation start."""
    request = _validated_request(SearchReservationRequest, body)
    if isinstance(request, VapiToolResponse):
        return _format_tool_response(body, request)
    response = _execute_tool(
        tool_name="search_reservation",
        request=request,
        operation=service.search_reservation,
        idempotency_key=idempotency_key,
    )
    return _format_tool_response(body, response)


@router.post("/modify")
def modify_reservation(
    body: Annotated[dict[str, Any], Body()],
    _: RequireVapiAuth,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    idempotency_key: IdempotencyHeader = None,
) -> dict[str, Any] | VapiToolResponse:
    """Modify an existing reservation after validating any changed booking slot."""
    request = _validated_request(ModifyReservationRequest, body)
    if isinstance(request, VapiToolResponse):
        return _format_tool_response(body, request)
    response = _execute_tool(
        tool_name="modify_reservation",
        request=request,
        operation=service.modify_reservation,
        idempotency_key=idempotency_key,
    )
    return _format_tool_response(body, response)


@router.post("/cancel")
def cancel_reservation(
    body: Annotated[dict[str, Any], Body()],
    _: RequireVapiAuth,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    idempotency_key: IdempotencyHeader = None,
) -> dict[str, Any] | VapiToolResponse:
    """Cancel an active reservation and leave it as a non-blocking record."""
    request = _validated_request(CancelReservationRequest, body)
    if isinstance(request, VapiToolResponse):
        return _format_tool_response(body, request)
    response = _execute_tool(
        tool_name="cancel_reservation",
        request=request,
        operation=service.cancel_reservation,
        idempotency_key=idempotency_key,
    )
    return _format_tool_response(body, response)


@router.post("/manager-followup")
def manager_followup(
    body: Annotated[dict[str, Any], Body()],
    _: RequireVapiAuth,
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: IdempotencyHeader = None,
) -> dict[str, Any] | VapiToolResponse:
    """Send collected failed-transfer details to the manager notification boundary."""
    request = _validated_request(ManagerFollowupRequest, body)
    if isinstance(request, VapiToolResponse):
        return _format_tool_response(body, request)

    def send_followup(followup_request: ManagerFollowupRequest) -> VapiToolResponse:
        notifier = build_manager_email_notifier(settings)
        notifier.send_manager_followup(followup_request)
        return VapiToolResponse(
            status=VapiToolStatus.ACCEPTED,
            message="Manager follow-up details were received.",
        )

    response = _execute_tool(
        tool_name="manager_followup",
        request=request,
        operation=send_followup,
        idempotency_key=idempotency_key,
    )
    return _format_tool_response(body, response)
