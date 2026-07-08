"""Schemas for staff dashboard APIs."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.resources import SeatingPreference


class StaffBaseModel(BaseModel):
    """Base model for strict staff API payload validation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StaffLoginRequest(StaffBaseModel):
    """Shared-password login request."""

    password: str = Field(..., min_length=1)


class StaffLoginResponse(StaffBaseModel):
    """Shared-password login response."""

    authenticated: bool


class StaffReservationStatus(StrEnum):
    """Dashboard reservation status values."""

    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class StaffReservationSource(StrEnum):
    """Reservation source values."""

    AI_CALL = "ai_call"
    STAFF_MANUAL = "staff_manual"
    WALK_IN = "walk_in"


class StaffReservationCreateRequest(StaffBaseModel):
    """Payload for manually creating a staff reservation."""

    customer_name: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1)
    party_size: int = Field(..., ge=1, le=99)
    reservation_start: datetime
    seating_preference: SeatingPreference = SeatingPreference.NO_PREFERENCE
    resource_id: str | None = None
    notes: str | None = None
    allergy_notes: str | None = None


class StaffReservationPatchRequest(StaffBaseModel):
    """Payload for editing a staff reservation."""

    expected_version: int = Field(..., ge=1)
    customer_name: str | None = None
    phone: str | None = None
    party_size: int | None = Field(default=None, ge=1, le=99)
    reservation_start: datetime | None = None
    seating_preference: SeatingPreference | None = None
    resource_id: str | None = None
    notes: str | None = None
    allergy_notes: str | None = None

    @model_validator(mode="after")
    def require_change(self) -> "StaffReservationPatchRequest":
        """Require at least one editable field."""
        if all(
            value is None
            for value in (
                self.customer_name,
                self.phone,
                self.party_size,
                self.reservation_start,
                self.seating_preference,
                self.resource_id,
                self.notes,
                self.allergy_notes,
            )
        ):
            raise ValueError("at least one change field is required")
        return self


class StaffVersionRequest(StaffBaseModel):
    """Payload for status mutations that use optimistic concurrency."""

    expected_version: int = Field(..., ge=1)


class StaffCompleteRequest(StaffVersionRequest):
    """Payload for completing a reservation or walk-in."""

    final_bill_krw: int = Field(..., ge=0)


class StaffWalkInCreateRequest(StaffBaseModel):
    """Payload for seating a walk-in immediately."""

    party_size: int = Field(..., ge=1, le=99)
    resource_id: str = Field(..., min_length=1)
    seated_at: datetime | None = None
    notes: str | None = None


class StaffFollowupUpdateRequest(StaffBaseModel):
    """Payload for updating manager follow-up status."""

    status: str = Field(..., pattern="^(open|resolved|cancelled)$")
    notes: str | None = None


class VapiCallLogCreateRequest(StaffBaseModel):
    """Payload for Vapi call-log storage."""

    call_time: datetime | None = None
    customer_phone: str | None = None
    transcript: str | None = None
    summary: str | None = None
    action_taken: str | None = None
    reservation_id: str | None = None

    @model_validator(mode="after")
    def require_transcript_or_summary(self) -> "VapiCallLogCreateRequest":
        """Require at least one reviewable call detail."""
        if not self.transcript and not self.summary:
            raise ValueError("transcript or summary is required")
        return self


class ReservationResponse(BaseModel):
    """Staff-facing reservation record."""

    id: str
    customer_name: str
    phone: str
    party_size: int
    reservation_start: datetime
    reservation_end: datetime
    seating_preference: str
    resource_ids: list[str]
    notes: str | None
    allergy_notes: str | None
    status: str
    source: str
    version: int
    final_bill_krw: int | None = None
    private_room_minimum_spend_krw: int | None = None
    actual_seated_at: datetime | None = None
    completed_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)


class ReservationListResponse(BaseModel):
    """List envelope for staff reservations."""

    items: list[ReservationResponse]


class FloorResourceResponse(BaseModel):
    """Resource status for the operational floor view."""

    id: str
    label: str
    resource_type: str
    capacity: int
    status: str
    current_reservation: ReservationResponse | None = None
    next_reservation: ReservationResponse | None = None


class FloorResponse(BaseModel):
    """Floor-state response for a selected date and time."""

    date: date
    selected_time: datetime
    resources: list[FloorResourceResponse]


class CustomerSummaryResponse(BaseModel):
    """Customer summary row."""

    id: str
    name: str
    phone: str
    preferences: str | None = None
    allergies: str | None = None
    staff_notes: str | None = None
    total_visits: int
    upcoming_bookings: int
    cancellations: int
    no_shows: int


class CustomerListResponse(BaseModel):
    """Customer search result envelope."""

    items: list[CustomerSummaryResponse]


class CustomerDetailResponse(CustomerSummaryResponse):
    """Customer profile response."""

    reservations: list[ReservationResponse]


class FollowupResponse(BaseModel):
    """Manager follow-up response."""

    id: str
    customer_name: str
    phone: str
    reason: str
    party_size: int | None = None
    reservation_start: datetime | None = None
    notes: str | None = None
    status: str


class FollowupListResponse(BaseModel):
    """Follow-up list response."""

    items: list[FollowupResponse]


class CallLogResponse(BaseModel):
    """Call-log response."""

    id: str
    call_time: datetime
    customer_phone: str | None = None
    transcript: str | None = None
    summary: str | None = None
    action_taken: str | None = None
    reservation_id: str | None = None


class CallLogListResponse(BaseModel):
    """Call-log list response."""

    items: list[CallLogResponse]


class ReportResponse(BaseModel):
    """Aggregated staff report response."""

    range: str
    start_date: date
    end_date: date
    metrics: dict[str, int | dict[str, int]]
    charts: dict[str, list[dict[str, int | str]]]


class BackupResponse(BaseModel):
    """Manual backup metadata response."""

    id: str
    file_path: str
    status: str
    message: str | None = None


class DemoResetResponse(BaseModel):
    """Demo reset result."""

    reset: bool
    reservations_created: int


class StaffEvent(BaseModel):
    """Live-update event payload."""

    type: str
    entity: str
    id: str
    version: int
    occurred_at: datetime

    @field_validator("type", "entity", "id")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        """Prevent unusable event identifiers."""
        if not value:
            raise ValueError("value must not be empty")
        return value
