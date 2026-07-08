"""Staff dashboard database operations and live update support."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.db.models import (
    AuditLogModel,
    BackupRunModel,
    CallLogModel,
    CustomerModel,
    ManagerFollowupModel,
    ReservationModel,
    ReservationResourceAssignment,
    ResourceMember,
    RestaurantResourceModel,
)
from app.db.seed import seed_restaurant_resources
from app.models.resources import ResourceType, SeatingPreference, private_room_minimum_spend_for_party_size
from app.schemas.staff import (
    StaffCompleteRequest,
    StaffEvent,
    StaffFollowupUpdateRequest,
    StaffReservationCreateRequest,
    StaffReservationPatchRequest,
    StaffReservationSource,
    StaffReservationStatus,
    StaffVersionRequest,
    StaffWalkInCreateRequest,
    VapiCallLogCreateRequest,
)
from app.services.notification_service import NoOpReservationNotifier, ReservationNotifier
from app.services.resource_allocator import reservations_overlap
from app.services.reservation_store import ReservationRecord
from app.utils.time import (
    SEOUL_TZ,
    ReservationTimeError,
    calculate_reservation_end,
    normalize_to_seoul,
    validate_reservation_start,
)


NON_BLOCKING_STATUSES = {
    StaffReservationStatus.CANCELLED.value,
    StaffReservationStatus.NO_SHOW.value,
}
MUTATION_ACTOR = "staff"


class StaffServiceError(Exception):
    """Base exception for staff service failures."""


class StaffNotFoundError(StaffServiceError):
    """Raised when a requested staff API record does not exist."""


class StaffConflictError(StaffServiceError):
    """Raised when optimistic concurrency or availability checks fail."""


class StaffValidationError(StaffServiceError):
    """Raised when a request is structurally valid but violates business rules."""


class StaffEventHub:
    """In-process WebSocket broadcaster for staff dashboard updates."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and track a staff WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Stop tracking a staff WebSocket connection."""
        self._connections.discard(websocket)

    async def broadcast(self, event: StaffEvent) -> None:
        """Send an event to all connected staff clients."""
        for websocket in list(self._connections):
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except RuntimeError:
                self.disconnect(websocket)


class StaffService:
    """Database-backed staff dashboard service."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker | Callable[[], Session],
        notifier: ReservationNotifier | None = None,
        event_hub: StaffEventHub | None = None,
        now_provider: Callable[[], datetime] | None = None,
        backup_dir: str | Path = "backups",
    ) -> None:
        self._session_factory = session_factory
        self.notifier = notifier or NoOpReservationNotifier()
        self.event_hub = event_hub or StaffEventHub()
        self._now_provider = now_provider or (lambda: datetime.now(SEOUL_TZ))
        self._backup_dir = Path(backup_dir)

    def list_reservations(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        day: date | None = None,
    ) -> list[dict[str, Any]]:
        """Return staff reservations, optionally filtered."""
        with self._session_factory() as session:
            statement = (
                select(ReservationModel)
                .options(joinedload(ReservationModel.resource_assignments))
                .order_by(ReservationModel.start_at, ReservationModel.id)
            )
            if status:
                statement = statement.where(ReservationModel.status == status)
            if query:
                like_query = f"%{query}%"
                statement = statement.where(
                    or_(
                        ReservationModel.customer_name.like(like_query),
                        ReservationModel.phone.like(like_query),
                    )
                )
            if day:
                start, end = self._day_bounds(day)
                statement = statement.where(
                    ReservationModel.start_at >= start,
                    ReservationModel.start_at < end,
                )
            reservations = session.scalars(statement).unique().all()
            return [self._reservation_response(reservation) for reservation in reservations]

    def get_reservation(self, reservation_id: str) -> dict[str, Any]:
        """Return one reservation."""
        with self._session_factory() as session:
            reservation = self._load_reservation(session, reservation_id)
            return self._reservation_response(reservation)

    def create_reservation(
        self,
        request: StaffReservationCreateRequest,
    ) -> tuple[dict[str, Any], StaffEvent]:
        """Create a staff manual reservation and send confirmation SMS."""
        start = self._validate_staff_start(request.reservation_start)
        end = calculate_reservation_end(start)
        with self._session_factory() as session:
            with session.begin():
                resource, resource_ids = self._resolve_resource_assignment(
                    session,
                    resource_id=request.resource_id,
                    party_size=request.party_size,
                    seating_preference=request.seating_preference,
                    start=start,
                    end=end,
                )
                self._assert_resources_available(
                    session,
                    resource_ids=resource_ids,
                    start=start,
                    end=end,
                )
                customer = self._get_or_create_customer(
                    session,
                    name=request.customer_name,
                    phone=request.phone,
                    allergy_notes=request.allergy_notes,
                )
                reservation = ReservationModel(
                    customer_id=customer.id,
                    customer_name=request.customer_name,
                    phone=request.phone,
                    party_size=request.party_size,
                    start_at=start,
                    end_at=end,
                    seating_preference=request.seating_preference.value,
                    notes=request.notes,
                    allergy_notes=request.allergy_notes,
                    private_room_minimum_spend_krw=self._minimum_spend(resource, request.party_size),
                    status=StaffReservationStatus.CONFIRMED.value,
                    source=StaffReservationSource.STAFF_MANUAL.value,
                    version=1,
                )
                session.add(reservation)
                session.flush()
                self._replace_assignments(session, reservation.id, resource_ids)
                session.flush()
                self._write_audit(
                    session,
                    action="reservation_create",
                    entity_type="reservation",
                    entity_id=reservation.id,
                    before=None,
                    after=self._reservation_audit_dict(reservation, resource_ids),
                )
            reservation = self._load_reservation(session, reservation.id)
            response = self._reservation_response(reservation)
            self.notifier.send_confirmation(self._notification_record(reservation))
            return response, self._event("reservation.created", response)

    def patch_reservation(
        self,
        reservation_id: str,
        request: StaffReservationPatchRequest,
    ) -> tuple[dict[str, Any], StaffEvent | None, bool]:
        """Edit a reservation with optimistic concurrency checks."""
        with self._session_factory() as session:
            with session.begin():
                reservation = self._load_reservation(session, reservation_id)
                self._assert_expected_version(reservation, request.expected_version)
                before = self._reservation_audit_dict(
                    reservation,
                    self._resource_ids(reservation),
                )
                old_start = normalize_to_seoul(reservation.start_at)
                old_phone = reservation.phone
                old_source = reservation.source

                if request.customer_name is not None:
                    reservation.customer_name = request.customer_name
                if request.phone is not None:
                    reservation.phone = request.phone
                if request.party_size is not None:
                    reservation.party_size = request.party_size
                if request.seating_preference is not None:
                    reservation.seating_preference = request.seating_preference.value
                if request.notes is not None:
                    reservation.notes = request.notes
                if request.allergy_notes is not None:
                    reservation.allergy_notes = request.allergy_notes

                if request.reservation_start is not None:
                    start = self._validate_staff_start(request.reservation_start)
                    reservation.start_at = start
                    reservation.end_at = calculate_reservation_end(start)

                seating_preference = SeatingPreference(reservation.seating_preference)
                resource, resource_ids = self._resolve_resource_assignment(
                    session,
                    resource_id=request.resource_id,
                    party_size=reservation.party_size,
                    seating_preference=seating_preference,
                    start=normalize_to_seoul(reservation.start_at),
                    end=normalize_to_seoul(reservation.end_at),
                    current_resource_ids=self._resource_ids(reservation),
                )
                self._assert_resources_available(
                    session,
                    resource_ids=resource_ids,
                    start=normalize_to_seoul(reservation.start_at),
                    end=normalize_to_seoul(reservation.end_at),
                    exclude_reservation_id=reservation.id,
                )
                reservation.private_room_minimum_spend_krw = self._minimum_spend(
                    resource,
                    reservation.party_size,
                )
                reservation.customer_id = self._get_or_create_customer(
                    session,
                    name=reservation.customer_name,
                    phone=reservation.phone,
                    allergy_notes=reservation.allergy_notes,
                ).id
                reservation.version += 1
                self._replace_assignments(session, reservation.id, resource_ids)
                session.flush()
                after = self._reservation_audit_dict(reservation, resource_ids)
                self._write_audit(
                    session,
                    action="reservation_update",
                    entity_type="reservation",
                    entity_id=reservation.id,
                    before=before,
                    after=after,
                )
                send_modification = (
                    old_source != StaffReservationSource.WALK_IN.value
                    and old_phone
                    and normalize_to_seoul(reservation.start_at) != old_start
                )
            reservation = self._load_reservation(session, reservation.id)
            response = self._reservation_response(reservation)
            if send_modification:
                self.notifier.send_modification(self._notification_record(reservation))
            return response, self._event("reservation.updated", response), send_modification

    def cancel_reservation(
        self,
        reservation_id: str,
        request: StaffVersionRequest,
    ) -> tuple[dict[str, Any], StaffEvent]:
        """Cancel a reservation or walk-in."""
        response = self._set_status(
            reservation_id=reservation_id,
            expected_version=request.expected_version,
            status=StaffReservationStatus.CANCELLED.value,
            action="reservation_cancel",
        )
        if response["source"] != StaffReservationSource.WALK_IN.value and response["phone"]:
            self.notifier.send_cancellation(self._record_from_response(response))
        return response, self._event("reservation.cancelled", response)

    def mark_arrived(
        self,
        reservation_id: str,
        request: StaffVersionRequest,
    ) -> tuple[dict[str, Any], StaffEvent]:
        """Mark a confirmed reservation as seated."""
        response = self._set_status(
            reservation_id=reservation_id,
            expected_version=request.expected_version,
            status=StaffReservationStatus.SEATED.value,
            action="reservation_arrive",
            actual_seated_at=self._now(),
        )
        return response, self._event("reservation.arrived", response)

    def complete_reservation(
        self,
        reservation_id: str,
        request: StaffCompleteRequest,
    ) -> tuple[dict[str, Any], StaffEvent]:
        """Complete a seated reservation or walk-in and store final bill."""
        response = self._set_status(
            reservation_id=reservation_id,
            expected_version=request.expected_version,
            status=StaffReservationStatus.COMPLETED.value,
            action="reservation_complete",
            final_bill_krw=request.final_bill_krw,
            completed_at=self._now(),
        )
        return response, self._event("reservation.completed", response)

    def mark_no_show(
        self,
        reservation_id: str,
        request: StaffVersionRequest,
    ) -> tuple[dict[str, Any], StaffEvent]:
        """Mark a reservation as no-show."""
        response = self._set_status(
            reservation_id=reservation_id,
            expected_version=request.expected_version,
            status=StaffReservationStatus.NO_SHOW.value,
            action="reservation_no_show",
        )
        return response, self._event("reservation.no_show", response)

    def create_walk_in(
        self,
        request: StaffWalkInCreateRequest,
    ) -> tuple[dict[str, Any], StaffEvent]:
        """Seat a walk-in when a full 100-minute window is free."""
        start = normalize_to_seoul(request.seated_at or self._now())
        end = calculate_reservation_end(start)
        with self._session_factory() as session:
            with session.begin():
                resource, resource_ids = self._resolve_resource_assignment(
                    session,
                    resource_id=request.resource_id,
                    party_size=request.party_size,
                    seating_preference=SeatingPreference.NO_PREFERENCE,
                    start=start,
                    end=end,
                )
                try:
                    self._assert_resources_available(
                        session,
                        resource_ids=resource_ids,
                        start=start,
                        end=end,
                    )
                except StaffConflictError as exc:
                    raise StaffConflictError(
                        "selected resource does not have a full 100-minute free window"
                    ) from exc

                reservation = ReservationModel(
                    customer_id=None,
                    customer_name="",
                    phone="",
                    party_size=request.party_size,
                    start_at=start,
                    end_at=end,
                    seating_preference=SeatingPreference.NO_PREFERENCE.value,
                    notes=request.notes,
                    private_room_minimum_spend_krw=self._minimum_spend(resource, request.party_size),
                    status=StaffReservationStatus.SEATED.value,
                    source=StaffReservationSource.WALK_IN.value,
                    actual_seated_at=start,
                    version=1,
                )
                session.add(reservation)
                session.flush()
                self._replace_assignments(session, reservation.id, resource_ids)
                session.flush()
                self._write_audit(
                    session,
                    action="walk_in_create",
                    entity_type="reservation",
                    entity_id=reservation.id,
                    before=None,
                    after=self._reservation_audit_dict(reservation, resource_ids),
                )
            reservation = self._load_reservation(session, reservation.id)
            response = self._reservation_response(reservation)
            return response, self._event("walk_in.created", response)

    def floor_state(self, *, selected_date: date, selected_time: time) -> dict[str, Any]:
        """Return floor resource status for a selected date/time."""
        selected_at = datetime.combine(selected_date, selected_time, tzinfo=SEOUL_TZ)
        day_start, day_end = self._day_bounds(selected_date)
        with self._session_factory() as session:
            resources = session.scalars(
                select(RestaurantResourceModel)
                .where(RestaurantResourceModel.is_active.is_(True))
                .order_by(RestaurantResourceModel.id)
            ).all()
            reservations = session.scalars(
                select(ReservationModel)
                .options(joinedload(ReservationModel.resource_assignments))
                .where(
                    ReservationModel.start_at < day_end,
                    ReservationModel.end_at > day_start,
                    ReservationModel.status.notin_(NON_BLOCKING_STATUSES),
                )
                .order_by(ReservationModel.start_at, ReservationModel.id)
            ).unique().all()

            resource_statuses = []
            for resource in resources:
                member_ids = self._resource_members(session, resource.id)
                current = self._current_reservation(reservations, member_ids, selected_at)
                upcoming = self._next_reservation(reservations, member_ids, selected_at)
                resource_statuses.append(
                    {
                        "id": resource.id,
                        "label": resource.label,
                        "resource_type": resource.resource_type,
                        "capacity": resource.capacity,
                        "status": "occupied" if current is not None else "empty",
                        "current_reservation": self._reservation_response(current) if current else None,
                        "next_reservation": self._reservation_response(upcoming) if upcoming else None,
                    }
                )

        return {
            "date": selected_date,
            "selected_time": selected_at,
            "resources": resource_statuses,
        }

    def list_customers(self, *, query: str | None = None) -> list[dict[str, Any]]:
        """Search customer profiles."""
        with self._session_factory() as session:
            statement = select(CustomerModel).order_by(CustomerModel.name, CustomerModel.id)
            if query:
                like_query = f"%{query}%"
                statement = statement.where(
                    or_(CustomerModel.name.like(like_query), CustomerModel.phone.like(like_query))
                )
            customers = session.scalars(statement).all()
            return [self._customer_summary(session, customer) for customer in customers]

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Return one customer profile."""
        with self._session_factory() as session:
            customer = session.get(CustomerModel, customer_id)
            if customer is None:
                raise StaffNotFoundError("customer not found")
            summary = self._customer_summary(session, customer)
            reservations = session.scalars(
                select(ReservationModel)
                .options(joinedload(ReservationModel.resource_assignments))
                .where(ReservationModel.customer_id == customer_id)
                .order_by(ReservationModel.start_at.desc(), ReservationModel.id)
            ).unique().all()
            return {**summary, "reservations": [self._reservation_response(item) for item in reservations]}

    def list_followups(self, *, status: str | None = None) -> list[dict[str, Any]]:
        """Return manager follow-ups."""
        with self._session_factory() as session:
            statement = select(ManagerFollowupModel).order_by(
                ManagerFollowupModel.created_at.desc(),
                ManagerFollowupModel.id,
            )
            if status:
                statement = statement.where(ManagerFollowupModel.status == status)
            followups = session.scalars(statement).all()
            return [self._followup_response(followup) for followup in followups]

    def update_followup(
        self,
        followup_id: str,
        request: StaffFollowupUpdateRequest,
    ) -> tuple[dict[str, Any], StaffEvent]:
        """Update a manager follow-up."""
        with self._session_factory() as session:
            with session.begin():
                followup = session.get(ManagerFollowupModel, followup_id)
                if followup is None:
                    raise StaffNotFoundError("follow-up not found")
                before = self._followup_response(followup)
                followup.status = request.status
                if request.notes is not None:
                    followup.notes = request.notes
                session.flush()
                after = self._followup_response(followup)
                self._write_audit(
                    session,
                    action="followup_update",
                    entity_type="manager_followup",
                    entity_id=followup.id,
                    before=before,
                    after=after,
                )
            response = self._followup_response(followup)
            event = StaffEvent(
                type="followup.updated",
                entity="manager_followup",
                id=followup.id,
                version=1,
                occurred_at=self._now(),
            )
            return response, event

    def create_call_log(self, request: VapiCallLogCreateRequest) -> dict[str, Any]:
        """Persist a Vapi call log."""
        with self._session_factory() as session:
            with session.begin():
                call_log = CallLogModel(
                    call_time=normalize_to_seoul(request.call_time or self._now()),
                    customer_phone=request.customer_phone,
                    transcript=request.transcript,
                    summary=request.summary,
                    action_taken=request.action_taken,
                    reservation_id=request.reservation_id,
                )
                session.add(call_log)
            return self._call_log_response(call_log)

    def list_call_logs(self) -> list[dict[str, Any]]:
        """Return call logs newest first."""
        with self._session_factory() as session:
            call_logs = session.scalars(
                select(CallLogModel).order_by(CallLogModel.call_time.desc(), CallLogModel.id)
            ).all()
            return [self._call_log_response(call_log) for call_log in call_logs]

    def report(self, *, report_range: str, start_date: date) -> dict[str, Any]:
        """Return reservation and revenue aggregates for a date range."""
        start, end = self._report_bounds(report_range, start_date)
        with self._session_factory() as session:
            reservations = session.scalars(
                select(ReservationModel)
                .options(joinedload(ReservationModel.resource_assignments))
                .where(ReservationModel.start_at >= start, ReservationModel.start_at < end)
            ).unique().all()

        source_mix = Counter(reservation.source for reservation in reservations)
        status_mix = Counter(reservation.status for reservation in reservations)
        revenue_by_day: defaultdict[str, int] = defaultdict(int)
        bookings_by_day: Counter[str] = Counter()
        resource_usage: Counter[str] = Counter()

        for reservation in reservations:
            day_key = normalize_to_seoul(reservation.start_at).date().isoformat()
            bookings_by_day[day_key] += 1
            if reservation.final_bill_krw:
                revenue_by_day[day_key] += reservation.final_bill_krw
            for assignment in reservation.resource_assignments:
                resource_usage[assignment.resource_id] += 1

        completed_visits = status_mix[StaffReservationStatus.COMPLETED.value]
        no_shows = status_mix[StaffReservationStatus.NO_SHOW.value]
        metrics: dict[str, int | dict[str, int]] = {
            "bookings": len(reservations),
            "completed_visits": completed_visits,
            "cancellations": status_mix[StaffReservationStatus.CANCELLED.value],
            "no_shows": no_shows,
            "party_size_total": sum(reservation.party_size for reservation in reservations),
            "revenue_krw": sum(reservation.final_bill_krw or 0 for reservation in reservations),
            "source_mix": dict(source_mix),
            "table_room_usage": dict(resource_usage),
        }
        charts = {
            "bookings_by_day": [
                {"date": day, "bookings": count} for day, count in sorted(bookings_by_day.items())
            ],
            "revenue_by_day": [
                {"date": day, "revenue_krw": amount} for day, amount in sorted(revenue_by_day.items())
            ],
            "no_show_rate": [
                {
                    "label": "range",
                    "percent": int((no_shows / len(reservations)) * 100) if reservations else 0,
                }
            ],
            "table_room_usage": [
                {"resource_id": resource_id, "count": count}
                for resource_id, count in sorted(resource_usage.items())
            ],
            "source_mix": [
                {"source": source, "count": count} for source, count in sorted(source_mix.items())
            ],
        }
        return {
            "range": report_range,
            "start_date": start.date(),
            "end_date": (end - timedelta(days=1)).date(),
            "metrics": metrics,
            "charts": charts,
        }

    def create_backup(self) -> dict[str, Any]:
        """Create a manual backup marker and metadata row."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = self._backup_dir / f"ai_receptionist_{self._now().strftime('%Y%m%d_%H%M%S')}.bak"
        backup_path.write_text("ABCD Steakhouse manual database backup placeholder\n", encoding="utf-8")
        with self._session_factory() as session:
            with session.begin():
                backup = BackupRunModel(
                    file_path=str(backup_path),
                    status="created",
                    message="Manual backup file created.",
                )
                session.add(backup)
            return {
                "id": backup.id,
                "file_path": backup.file_path,
                "status": backup.status,
                "message": backup.message,
            }

    def reset_demo_data(self) -> dict[str, Any]:
        """Clear fictional demo data and reseed a sample day."""
        with self._session_factory() as session:
            session.execute(delete(ReservationResourceAssignment))
            session.execute(delete(ReservationModel))
            session.execute(delete(CallLogModel))
            session.execute(delete(ManagerFollowupModel))
            session.execute(delete(CustomerModel))
            session.commit()
            seed_restaurant_resources(session)

            with session.begin():
                customer = CustomerModel(
                    name="Demo Guest",
                    phone="+821055501111",
                    allergies="none",
                )
                session.add(customer)
                session.flush()
                reservation = ReservationModel(
                    customer_id=customer.id,
                    customer_name=customer.name,
                    phone=customer.phone,
                    party_size=4,
                    start_at=datetime(2026, 7, 1, 18, 0, tzinfo=SEOUL_TZ),
                    end_at=datetime(2026, 7, 1, 19, 40, tzinfo=SEOUL_TZ),
                    seating_preference=SeatingPreference.NO_PREFERENCE.value,
                    status=StaffReservationStatus.CONFIRMED.value,
                    source=StaffReservationSource.STAFF_MANUAL.value,
                    version=1,
                )
                session.add(reservation)
                session.flush()
                self._replace_assignments(session, reservation.id, ("table_3",))
                self._write_audit(
                    session,
                    action="demo_reset",
                    entity_type="demo_data",
                    entity_id="demo",
                    before=None,
                    after={"reservations_created": 1},
                )
        return {"reset": True, "reservations_created": 1}

    def _set_status(
        self,
        *,
        reservation_id: str,
        expected_version: int,
        status: str,
        action: str,
        actual_seated_at: datetime | None = None,
        completed_at: datetime | None = None,
        final_bill_krw: int | None = None,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            with session.begin():
                reservation = self._load_reservation(session, reservation_id)
                self._assert_expected_version(reservation, expected_version)
                before = self._reservation_audit_dict(reservation, self._resource_ids(reservation))
                reservation.status = status
                if actual_seated_at is not None:
                    reservation.actual_seated_at = normalize_to_seoul(actual_seated_at)
                if completed_at is not None:
                    reservation.completed_at = normalize_to_seoul(completed_at)
                    if reservation.source == StaffReservationSource.WALK_IN.value:
                        reservation.end_at = normalize_to_seoul(completed_at)
                if final_bill_krw is not None:
                    reservation.final_bill_krw = final_bill_krw
                reservation.version += 1
                session.flush()
                after = self._reservation_audit_dict(reservation, self._resource_ids(reservation))
                self._write_audit(
                    session,
                    action=action,
                    entity_type="reservation",
                    entity_id=reservation.id,
                    before=before,
                    after=after,
                )
            reservation = self._load_reservation(session, reservation.id)
            return self._reservation_response(reservation)

    def _event(self, event_type: str, response: dict[str, Any]) -> StaffEvent:
        return StaffEvent(
            type=event_type,
            entity="reservation",
            id=response["id"],
            version=response["version"],
            occurred_at=self._now(),
        )

    def _load_reservation(self, session: Session, reservation_id: str) -> ReservationModel:
        reservation = session.scalars(
            select(ReservationModel)
            .options(joinedload(ReservationModel.resource_assignments))
            .where(ReservationModel.id == reservation_id)
            .execution_options(populate_existing=True)
        ).unique().first()
        if reservation is None:
            raise StaffNotFoundError("reservation not found")
        return reservation

    def _validate_staff_start(self, value: datetime) -> datetime:
        try:
            return validate_reservation_start(value, now=self._now())
        except ReservationTimeError as exc:
            raise StaffValidationError(str(exc)) from exc

    def _resolve_resource_assignment(
        self,
        session: Session,
        *,
        resource_id: str | None,
        party_size: int,
        seating_preference: SeatingPreference,
        start: datetime,
        end: datetime,
        current_resource_ids: tuple[str, ...] = (),
    ) -> tuple[RestaurantResourceModel, tuple[str, ...]]:
        if resource_id is None and current_resource_ids:
            resource_id = self._resource_id_for_assignment(session, current_resource_ids)
        if resource_id is None:
            resource_id = self._auto_select_resource(
                session,
                party_size=party_size,
                seating_preference=seating_preference,
                start=start,
                end=end,
            )

        resource = session.get(RestaurantResourceModel, resource_id)
        if resource is None or not resource.is_active:
            raise StaffValidationError("resource not found")
        if resource.capacity < party_size:
            raise StaffValidationError("resource capacity is too small for party size")

        members = self._resource_members(session, resource_id)
        return resource, members

    def _auto_select_resource(
        self,
        session: Session,
        *,
        party_size: int,
        seating_preference: SeatingPreference,
        start: datetime,
        end: datetime,
    ) -> str:
        resource_types = (
            {ResourceType.PRIVATE_ROOM.value, ResourceType.COMBINED_PRIVATE_ROOM.value}
            if seating_preference == SeatingPreference.PRIVATE_ROOM
            else {ResourceType.REGULAR_TABLE.value, ResourceType.COMBINED_TABLE.value}
        )
        resources = session.scalars(
            select(RestaurantResourceModel)
            .where(
                RestaurantResourceModel.is_active.is_(True),
                RestaurantResourceModel.resource_type.in_(resource_types),
                RestaurantResourceModel.capacity >= party_size,
            )
            .order_by(RestaurantResourceModel.capacity, RestaurantResourceModel.id)
        ).all()
        for resource in resources:
            resource_ids = self._resource_members(session, resource.id)
            try:
                self._assert_resources_available(
                    session,
                    resource_ids=resource_ids,
                    start=start,
                    end=end,
                )
            except StaffConflictError:
                continue
            return resource.id
        raise StaffConflictError("no resource is available for that time")

    def _resource_members(self, session: Session, resource_id: str) -> tuple[str, ...]:
        members = tuple(
            session.scalars(
                select(ResourceMember.member_resource_id)
                .where(ResourceMember.resource_id == resource_id)
                .order_by(ResourceMember.member_resource_id)
            ).all()
        )
        return members or (resource_id,)

    def _resource_id_for_assignment(
        self,
        session: Session,
        resource_ids: tuple[str, ...],
    ) -> str:
        resource_set = set(resource_ids)
        resources = session.scalars(
            select(RestaurantResourceModel).where(RestaurantResourceModel.is_active.is_(True))
        ).all()
        for resource in resources:
            if set(self._resource_members(session, resource.id)) == resource_set:
                return resource.id
        return resource_ids[0]

    def _assert_resources_available(
        self,
        session: Session,
        *,
        resource_ids: tuple[str, ...],
        start: datetime,
        end: datetime,
        exclude_reservation_id: str | None = None,
    ) -> None:
        candidate_ids = set(resource_ids)
        reservations = session.scalars(
            select(ReservationModel)
            .options(joinedload(ReservationModel.resource_assignments))
            .where(
                ReservationModel.start_at < end,
                ReservationModel.end_at > start,
                ReservationModel.status.notin_(NON_BLOCKING_STATUSES),
            )
        ).unique().all()
        for reservation in reservations:
            if reservation.id == exclude_reservation_id:
                continue
            if not reservations_overlap(
                normalize_to_seoul(reservation.start_at),
                normalize_to_seoul(reservation.end_at),
                start,
                end,
            ):
                continue
            if candidate_ids.intersection(self._resource_ids(reservation)):
                raise StaffConflictError("resource is already booked for that time")

    def _assert_expected_version(self, reservation: ReservationModel, expected_version: int) -> None:
        if reservation.version != expected_version:
            raise StaffConflictError("record changed, reload before saving")

    def _replace_assignments(
        self,
        session: Session,
        reservation_id: str,
        resource_ids: tuple[str, ...],
    ) -> None:
        session.execute(
            delete(ReservationResourceAssignment).where(
                ReservationResourceAssignment.reservation_id == reservation_id
            )
        )
        for resource_id in resource_ids:
            session.add(
                ReservationResourceAssignment(
                    reservation_id=reservation_id,
                    resource_id=resource_id,
                )
            )

    def _get_or_create_customer(
        self,
        session: Session,
        *,
        name: str,
        phone: str,
        allergy_notes: str | None,
    ) -> CustomerModel:
        customer = session.scalars(
            select(CustomerModel).where(CustomerModel.phone == phone, CustomerModel.name == name)
        ).first()
        if customer is not None:
            if allergy_notes:
                customer.allergies = allergy_notes
            return customer

        customer = CustomerModel(name=name, phone=phone, allergies=allergy_notes)
        session.add(customer)
        session.flush()
        return customer

    def _minimum_spend(self, resource: RestaurantResourceModel, party_size: int) -> int | None:
        if resource.resource_type in {
            ResourceType.PRIVATE_ROOM.value,
            ResourceType.COMBINED_PRIVATE_ROOM.value,
        }:
            return private_room_minimum_spend_for_party_size(party_size)
        return None

    def _resource_ids(self, reservation: ReservationModel) -> tuple[str, ...]:
        return tuple(
            assignment.resource_id
            for assignment in sorted(
                reservation.resource_assignments,
                key=lambda assignment: assignment.id,
            )
        )

    def _reservation_response(self, reservation: ReservationModel) -> dict[str, Any]:
        warnings: list[str] = []
        if (
            reservation.final_bill_krw is not None
            and reservation.private_room_minimum_spend_krw is not None
            and reservation.final_bill_krw < reservation.private_room_minimum_spend_krw
        ):
            warnings.append("final_bill_below_private_room_minimum")
        return {
            "id": reservation.id,
            "customer_name": reservation.customer_name,
            "phone": reservation.phone,
            "party_size": reservation.party_size,
            "reservation_start": normalize_to_seoul(reservation.start_at),
            "reservation_end": normalize_to_seoul(reservation.end_at),
            "seating_preference": reservation.seating_preference,
            "resource_ids": list(self._resource_ids(reservation)),
            "notes": reservation.notes,
            "allergy_notes": reservation.allergy_notes,
            "status": reservation.status,
            "source": reservation.source,
            "version": reservation.version,
            "final_bill_krw": reservation.final_bill_krw,
            "private_room_minimum_spend_krw": reservation.private_room_minimum_spend_krw,
            "actual_seated_at": normalize_to_seoul(reservation.actual_seated_at)
            if reservation.actual_seated_at
            else None,
            "completed_at": normalize_to_seoul(reservation.completed_at)
            if reservation.completed_at
            else None,
            "warnings": warnings,
        }

    def _notification_record(self, reservation: ReservationModel) -> ReservationRecord:
        return ReservationRecord(
            id=reservation.id,
            customer_name=reservation.customer_name,
            phone=reservation.phone,
            party_size=reservation.party_size,
            start=normalize_to_seoul(reservation.start_at),
            end=normalize_to_seoul(reservation.end_at),
            seating_preference=SeatingPreference(reservation.seating_preference),
            resource_ids=self._resource_ids(reservation),
            notes=reservation.notes,
            allergy_notes=reservation.allergy_notes,
            private_room_minimum_spend_krw=reservation.private_room_minimum_spend_krw,
            status=reservation.status,
            source=reservation.source,
            version=reservation.version,
        )

    def _record_from_response(self, response: dict[str, Any]) -> ReservationRecord:
        return ReservationRecord(
            id=response["id"],
            customer_name=response["customer_name"],
            phone=response["phone"],
            party_size=response["party_size"],
            start=response["reservation_start"],
            end=response["reservation_end"],
            seating_preference=SeatingPreference(response["seating_preference"]),
            resource_ids=tuple(response["resource_ids"]),
            notes=response["notes"],
            allergy_notes=response["allergy_notes"],
            private_room_minimum_spend_krw=response["private_room_minimum_spend_krw"],
            status=response["status"],
            source=response["source"],
            version=response["version"],
        )

    def _reservation_audit_dict(
        self,
        reservation: ReservationModel,
        resource_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        return {
            "id": reservation.id,
            "customer_name": reservation.customer_name,
            "phone": reservation.phone,
            "party_size": reservation.party_size,
            "start_at": normalize_to_seoul(reservation.start_at).isoformat(),
            "end_at": normalize_to_seoul(reservation.end_at).isoformat(),
            "resource_ids": list(resource_ids),
            "status": reservation.status,
            "source": reservation.source,
            "version": reservation.version,
            "final_bill_krw": reservation.final_bill_krw,
        }

    def _write_audit(
        self,
        session: Session,
        *,
        action: str,
        entity_type: str,
        entity_id: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        session.add(
            AuditLogModel(
                actor=MUTATION_ACTOR,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before_json=json.dumps(before, sort_keys=True) if before is not None else None,
                after_json=json.dumps(after, sort_keys=True) if after is not None else None,
            )
        )

    def _customer_summary(self, session: Session, customer: CustomerModel) -> dict[str, Any]:
        reservations = session.scalars(
            select(ReservationModel)
            .options(joinedload(ReservationModel.resource_assignments))
            .where(ReservationModel.customer_id == customer.id)
        ).unique().all()
        return {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "preferences": customer.preferences,
            "allergies": customer.allergies,
            "staff_notes": customer.staff_notes,
            "total_visits": sum(
                1 for reservation in reservations if reservation.status == StaffReservationStatus.COMPLETED.value
            ),
            "upcoming_bookings": sum(
                1 for reservation in reservations if reservation.status == StaffReservationStatus.CONFIRMED.value
            ),
            "cancellations": sum(
                1 for reservation in reservations if reservation.status == StaffReservationStatus.CANCELLED.value
            ),
            "no_shows": sum(
                1 for reservation in reservations if reservation.status == StaffReservationStatus.NO_SHOW.value
            ),
        }

    def _followup_response(self, followup: ManagerFollowupModel) -> dict[str, Any]:
        return {
            "id": followup.id,
            "customer_name": followup.customer_name,
            "phone": followup.phone,
            "reason": followup.reason,
            "party_size": followup.party_size,
            "reservation_start": normalize_to_seoul(followup.reservation_start)
            if followup.reservation_start
            else None,
            "notes": followup.notes,
            "status": followup.status,
        }

    def _call_log_response(self, call_log: CallLogModel) -> dict[str, Any]:
        return {
            "id": call_log.id,
            "call_time": normalize_to_seoul(call_log.call_time),
            "customer_phone": call_log.customer_phone,
            "transcript": call_log.transcript,
            "summary": call_log.summary,
            "action_taken": call_log.action_taken,
            "reservation_id": call_log.reservation_id,
        }

    def _current_reservation(
        self,
        reservations: Iterable[ReservationModel],
        resource_ids: tuple[str, ...],
        selected_at: datetime,
    ) -> ReservationModel | None:
        resource_set = set(resource_ids)
        for reservation in reservations:
            if not resource_set.intersection(self._resource_ids(reservation)):
                continue
            if normalize_to_seoul(reservation.start_at) <= selected_at < normalize_to_seoul(reservation.end_at):
                return reservation
        return None

    def _next_reservation(
        self,
        reservations: Iterable[ReservationModel],
        resource_ids: tuple[str, ...],
        selected_at: datetime,
    ) -> ReservationModel | None:
        resource_set = set(resource_ids)
        upcoming = [
            reservation
            for reservation in reservations
            if resource_set.intersection(self._resource_ids(reservation))
            and normalize_to_seoul(reservation.start_at) > selected_at
        ]
        return min(upcoming, key=lambda reservation: reservation.start_at) if upcoming else None

    def _report_bounds(self, report_range: str, start_date: date) -> tuple[datetime, datetime]:
        start = datetime.combine(start_date, time.min, tzinfo=SEOUL_TZ)
        if report_range == "daily":
            return start, start + timedelta(days=1)
        if report_range == "weekly":
            return start, start + timedelta(days=7)
        if report_range == "monthly":
            month = 1 if start.month == 12 else start.month + 1
            year = start.year + 1 if start.month == 12 else start.year
            return start, datetime(year, month, 1, tzinfo=SEOUL_TZ)
        if report_range == "yearly":
            return start, datetime(start.year + 1, 1, 1, tzinfo=SEOUL_TZ)
        raise StaffValidationError("range must be daily, weekly, monthly, or yearly")

    def _day_bounds(self, day: date) -> tuple[datetime, datetime]:
        start = datetime.combine(day, time.min, tzinfo=SEOUL_TZ)
        return start, start + timedelta(days=1)

    def _now(self) -> datetime:
        return normalize_to_seoul(self._now_provider())
