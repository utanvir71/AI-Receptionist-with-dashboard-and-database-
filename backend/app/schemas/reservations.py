"""Reservation API schemas."""

from datetime import datetime
from enum import StrEnum
import re
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.resources import SeatingPreference


PHONE_E164_PATTERN = r"^\+[1-9]\d{7,14}$"


class VapiToolStatus(StrEnum):
    """Stable response status values for Vapi-facing endpoints."""

    ACCEPTED = "accepted"
    AVAILABLE = "available"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    INVALID_REQUEST = "invalid_request"
    OUTSIDE_RESERVATION_HOURS = "outside_reservation_hours"
    PRIVATE_ROOM_REQUIRED = "private_room_required"
    CONFLICT = "conflict"
    MANAGER_REQUIRED = "manager_required"
    UNAUTHORIZED = "unauthorized"
    ERROR = "error"


class ReservationBaseModel(BaseModel):
    """Base model for strict Vapi tool payload validation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PhonePayload(ReservationBaseModel):
    """Payload mixin requiring a normalized E.164 phone number."""

    phone: str = Field(..., description="Customer phone in E.164 format")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Return a clearer message than a raw regex failure."""
        if not re.fullmatch(PHONE_E164_PATTERN, value):
            raise ValueError("phone must use E.164 format, for example +821012345678")
        return value


class ReservationLookupPayload(PhonePayload):
    """Fields used to identify an existing reservation."""

    reservation_start: datetime
    customer_name: str | None = None


class CheckAvailabilityRequest(ReservationBaseModel):
    """Request body for checking table or room availability."""

    party_size: int = Field(..., ge=1, le=99)
    reservation_start: datetime
    seating_preference: SeatingPreference
    notes: str | None = None


class CreateReservationRequest(PhonePayload):
    """Request body for creating a confirmed reservation."""

    customer_name: str = Field(..., min_length=1)
    party_size: int = Field(..., ge=1, le=99)
    reservation_start: datetime
    seating_preference: SeatingPreference
    notes: str | None = None
    allergy_notes: str | None = None
    call_id: str | None = None


class SearchReservationRequest(ReservationLookupPayload):
    """Request body for searching an existing reservation."""


class CancelReservationRequest(ReservationLookupPayload):
    """Request body for cancelling an existing reservation."""


class ModifyReservationRequest(PhonePayload):
    """Request body for modifying an existing reservation."""

    original_reservation_start: datetime
    new_reservation_start: datetime | None = None
    new_party_size: int | None = Field(default=None, ge=1, le=99)
    new_customer_name: str | None = None
    new_phone: str | None = None
    new_seating_preference: SeatingPreference | None = None
    new_notes: str | None = None
    new_allergy_notes: str | None = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> Self:
        """Require one explicit modification field."""
        change_fields = (
            self.new_reservation_start,
            self.new_party_size,
            self.new_customer_name,
            self.new_phone,
            self.new_seating_preference,
            self.new_notes,
            self.new_allergy_notes,
        )
        if all(value is None for value in change_fields):
            raise ValueError("at least one change field is required")
        return self

    @field_validator("new_phone")
    @classmethod
    def validate_new_phone(cls, value: str | None) -> str | None:
        """Validate optional replacement phone numbers."""
        if value is not None and not re.fullmatch(PHONE_E164_PATTERN, value):
            raise ValueError("new_phone must use E.164 format, for example +821012345678")
        return value


class ManagerFollowupRequest(PhonePayload):
    """Request body for manager follow-up after failed transfer or escalation."""

    customer_name: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    party_size: int | None = Field(default=None, ge=1, le=99)
    reservation_start: datetime | None = None
    notes: str | None = None


class VapiToolResponse(ReservationBaseModel):
    """Caller-safe response envelope for Vapi tools."""

    status: VapiToolStatus
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
