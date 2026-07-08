"""Vapi call-log storage endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.api.staff.router import get_staff_service
from app.core.security import require_vapi_authorization
from app.schemas.staff import CallLogResponse, VapiCallLogCreateRequest
from app.services.staff_service import StaffService


router = APIRouter()

RequireVapiAuth = Annotated[None, Depends(require_vapi_authorization)]


@router.post("", response_model=CallLogResponse, status_code=status.HTTP_201_CREATED)
def create_call_log(
    request: VapiCallLogCreateRequest,
    _: RequireVapiAuth,
    service: Annotated[StaffService, Depends(get_staff_service)],
) -> dict[str, Any]:
    """Store Vapi call transcript or summary data."""
    return service.create_call_log(request)
