"""Reservation workflow orchestration service."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
import logging

from app.models.resources import SeatingPreference
from app.schemas.reservations import (
    CancelReservationRequest,
    CheckAvailabilityRequest,
    CreateReservationRequest,
    ModifyReservationRequest,
    SearchReservationRequest,
    VapiToolResponse,
    VapiToolStatus,
)
from app.services.calendar_service import (
    CANCELLED_STATUS,
    ReservationCalendar,
    ReservationRecord,
)
from app.services.notification_service import NoOpReservationNotifier, ReservationNotifier
from app.services.resource_allocator import (
    AllocationOutcome,
    AllocationStatus,
    ExistingReservation,
    allocate_resource,
)
from app.utils.time import (
    SEOUL_TZ,
    ReservationTimeError,
    calculate_reservation_end,
    validate_reservation_start,
)


logger = logging.getLogger(__name__)

NEARBY_OPTION_OFFSETS = (
    timedelta(minutes=30),
    timedelta(minutes=-30),
    timedelta(minutes=60),
    timedelta(minutes=-60),
    timedelta(minutes=90),
    timedelta(minutes=-90),
    timedelta(minutes=120),
    timedelta(minutes=-120),
)


class ReservationService:
    """Coordinate validation, resource allocation, and calendar persistence."""

    def __init__(
        self,
        *,
        calendar: ReservationCalendar,
        notifier: ReservationNotifier | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.calendar = calendar
        self.notifier = notifier or NoOpReservationNotifier()
        self._now_provider = now_provider or (lambda: datetime.now(SEOUL_TZ))

    def check_availability(self, request: CheckAvailabilityRequest) -> VapiToolResponse:
        start = self._validate_start_for_response(request.reservation_start)
        if isinstance(start, VapiToolResponse):
            return start

        end = calculate_reservation_end(start)
        outcome = self._allocate(
            party_size=request.party_size,
            seating_preference=request.seating_preference,
            start=start,
            end=end,
        )
        return self._availability_response(
            outcome=outcome,
            party_size=request.party_size,
            seating_preference=request.seating_preference,
            start=start,
            end=end,
        )

    def create_reservation(self, request: CreateReservationRequest) -> VapiToolResponse:
        start = self._validate_start_for_response(request.reservation_start)
        if isinstance(start, VapiToolResponse):
            return start

        end = calculate_reservation_end(start)
        outcome = self._allocate(
            party_size=request.party_size,
            seating_preference=request.seating_preference,
            start=start,
            end=end,
        )
        if outcome.status != AllocationStatus.AVAILABLE or outcome.resource is None:
            return self._availability_response(
                outcome=outcome,
                party_size=request.party_size,
                seating_preference=request.seating_preference,
                start=start,
                end=end,
            )

        record = ReservationRecord(
            customer_name=request.customer_name,
            phone=request.phone,
            party_size=request.party_size,
            start=start,
            end=end,
            seating_preference=request.seating_preference,
            resource_ids=outcome.resource.members,
            notes=request.notes,
            allergy_notes=request.allergy_notes,
            call_id=request.call_id,
            private_room_minimum_spend_krw=outcome.private_room_minimum_spend_krw,
        )
        record = self.calendar.create_reservation(record)
        self._send_sms_notification("confirmation", record)

        return VapiToolResponse(
            status=VapiToolStatus.CONFIRMED,
            message="Reservation confirmed.",
            data=self._record_response_data(record),
        )

    def search_reservation(self, request: SearchReservationRequest) -> VapiToolResponse:
        records = self._find_active_records(
            phone=request.phone,
            reservation_start=request.reservation_start,
            customer_name=request.customer_name,
        )
        return self._search_response(records)

    def cancel_reservation(self, request: CancelReservationRequest) -> VapiToolResponse:
        records = self._find_active_records(
            phone=request.phone,
            reservation_start=request.reservation_start,
            customer_name=request.customer_name,
        )
        if len(records) != 1:
            return self._search_response(records)

        record = records[0]
        record.status = CANCELLED_STATUS
        record = self.calendar.update_reservation(record)
        self._send_sms_notification("cancellation", record)
        return VapiToolResponse(
            status=VapiToolStatus.CANCELLED,
            message="Reservation cancelled.",
            data=self._record_response_data(record),
        )

    def modify_reservation(self, request: ModifyReservationRequest) -> VapiToolResponse:
        records = self._find_active_records(
            phone=request.phone,
            reservation_start=request.original_reservation_start,
        )
        if len(records) != 1:
            return self._search_response(records)

        original = records[0]
        start = request.new_reservation_start or original.start
        validated_start = self._validate_start_for_response(start)
        if isinstance(validated_start, VapiToolResponse):
            return validated_start

        party_size = request.new_party_size or original.party_size
        seating_preference = request.new_seating_preference or original.seating_preference
        end = calculate_reservation_end(validated_start)
        outcome = self._allocate(
            party_size=party_size,
            seating_preference=seating_preference,
            start=validated_start,
            end=end,
            exclude_reservation_id=original.id,
        )
        if outcome.status != AllocationStatus.AVAILABLE or outcome.resource is None:
            return self._availability_response(
                outcome=outcome,
                party_size=party_size,
                seating_preference=seating_preference,
                start=validated_start,
                end=end,
            )

        updated = replace(
            original,
            customer_name=request.new_customer_name or original.customer_name,
            phone=request.new_phone or original.phone,
            party_size=party_size,
            start=validated_start,
            end=end,
            seating_preference=seating_preference,
            resource_ids=outcome.resource.members,
            private_room_minimum_spend_krw=outcome.private_room_minimum_spend_krw,
        )
        if request.new_notes is not None:
            updated.notes = request.new_notes
        if request.new_allergy_notes is not None:
            updated.allergy_notes = request.new_allergy_notes

        updated = self.calendar.update_reservation(updated)
        self._send_sms_notification("modification", updated)
        return VapiToolResponse(
            status=VapiToolStatus.CONFIRMED,
            message="Reservation updated.",
            data=self._record_response_data(updated),
        )

    def _validate_start_for_response(self, value: datetime) -> datetime | VapiToolResponse:
        try:
            return validate_reservation_start(value, now=self._now_provider())
        except ReservationTimeError as exc:
            if "outside reservation hours" in str(exc):
                return VapiToolResponse(
                    status=VapiToolStatus.OUTSIDE_RESERVATION_HOURS,
                    message=(
                        "Reservations are available from 11:00 to 14:30 and 17:00 to 19:30."
                    ),
                )
            return VapiToolResponse(
                status=VapiToolStatus.INVALID_REQUEST,
                message="That reservation time is in the past.",
            )

    def _allocate(
        self,
        *,
        party_size: int,
        seating_preference: SeatingPreference,
        start: datetime,
        end: datetime,
        exclude_reservation_id: str | None = None,
    ) -> AllocationOutcome:
        existing = [
            ExistingReservation(
                resource_ids=record.resource_ids,
                start=record.start,
                end=record.end,
                status=record.status,
            )
            for record in self.calendar.list_reservations(start=start, end=end)
            if record.id != exclude_reservation_id
        ]
        return allocate_resource(
            party_size=party_size,
            seating_preference=seating_preference,
            start=start,
            end=end,
            existing_reservations=existing,
        )

    def _availability_response(
        self,
        *,
        outcome: AllocationOutcome,
        party_size: int,
        seating_preference: SeatingPreference,
        start: datetime,
        end: datetime,
    ) -> VapiToolResponse:
        if outcome.status == AllocationStatus.AVAILABLE:
            data: dict[str, object] = {
                "reservation_start": start.isoformat(),
                "reservation_end": end.isoformat(),
            }
            if outcome.private_room_minimum_spend_krw is not None:
                data["private_room_minimum_spend_krw"] = outcome.private_room_minimum_spend_krw
            return VapiToolResponse(
                status=VapiToolStatus.AVAILABLE,
                message="That time is available.",
                data=data,
            )

        if outcome.status == AllocationStatus.PRIVATE_ROOM_REQUIRED:
            return VapiToolResponse(
                status=VapiToolStatus.PRIVATE_ROOM_REQUIRED,
                message="Regular seating is not available for this party size.",
                data={
                    "next_action": "ask_private_room_preference",
                    "private_room_requirements": {
                        "requires_steak_order": True,
                        "minimum_spend_krw": 600_000,
                    },
                },
            )

        if outcome.status == AllocationStatus.MANAGER_REQUIRED:
            return VapiToolResponse(
                status=VapiToolStatus.MANAGER_REQUIRED,
                message="A manager is required for this request.",
                data={"next_action": "collect_details_and_transfer_to_manager"},
            )

        return VapiToolResponse(
            status=VapiToolStatus.UNAVAILABLE,
            message="That time is not available.",
            data={
                "nearby_options": self._nearby_options(
                    party_size=party_size,
                    seating_preference=seating_preference,
                    requested_start=start,
                ),
                "loop_policy": "offer_nearby_once_then_ask_new_datetime",
            },
        )

    def _nearby_options(
        self,
        *,
        party_size: int,
        seating_preference: SeatingPreference,
        requested_start: datetime,
    ) -> list[str]:
        options: list[str] = []
        seen: set[datetime] = set()
        for offset in NEARBY_OPTION_OFFSETS:
            candidate_start = requested_start + offset
            if candidate_start.date() != requested_start.date() or candidate_start in seen:
                continue
            seen.add(candidate_start)
            try:
                candidate_start = validate_reservation_start(
                    candidate_start,
                    now=self._now_provider(),
                )
            except ReservationTimeError:
                continue

            candidate_end = calculate_reservation_end(candidate_start)
            outcome = self._allocate(
                party_size=party_size,
                seating_preference=seating_preference,
                start=candidate_start,
                end=candidate_end,
            )
            if outcome.status == AllocationStatus.AVAILABLE:
                options.append(candidate_start.isoformat())
            if len(options) == 3:
                break
        return options

    def _find_active_records(
        self,
        *,
        phone: str,
        reservation_start: datetime,
        customer_name: str | None = None,
    ) -> list[ReservationRecord]:
        return self.calendar.find_reservations(
            phone=phone,
            reservation_start=reservation_start,
            customer_name=customer_name,
        )

    def _search_response(self, records: list[ReservationRecord]) -> VapiToolResponse:
        if not records:
            return VapiToolResponse(
                status=VapiToolStatus.NOT_FOUND,
                message="No active reservation was found for that phone number and time.",
            )
        if len(records) > 1:
            return VapiToolResponse(
                status=VapiToolStatus.AMBIGUOUS,
                message="Multiple reservations matched. Ask for the customer name.",
            )
        record = records[0]
        return VapiToolResponse(
            status=VapiToolStatus.CONFIRMED,
            message="Reservation found.",
            data=self._record_response_data(record),
        )

    def _record_response_data(self, record: ReservationRecord) -> dict[str, object]:
        data: dict[str, object] = {
            "reservation_id": record.id,
            "customer_name": record.customer_name,
            "phone": record.phone,
            "party_size": record.party_size,
            "reservation_start": record.start.isoformat(),
            "reservation_end": record.end.isoformat(),
            "seating_preference": record.seating_preference.value,
            "notes": record.notes,
            "allergy_notes": record.allergy_notes,
            "status": record.status,
        }
        if record.private_room_minimum_spend_krw is not None:
            data["private_room_minimum_spend_krw"] = record.private_room_minimum_spend_krw
        return data

    def _send_sms_notification(self, notification_type: str, record: ReservationRecord) -> None:
        try:
            if notification_type == "confirmation":
                self.notifier.send_confirmation(record)
            elif notification_type == "modification":
                self.notifier.send_modification(record)
            elif notification_type == "cancellation":
                self.notifier.send_cancellation(record)
        except Exception as exc:
            logger.warning(
                "SMS %s failed for reservation %s: %s",
                notification_type,
                record.id,
                exc,
            )
