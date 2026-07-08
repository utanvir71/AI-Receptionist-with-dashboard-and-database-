"""Table and private-room availability allocation service."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.models.resources import (
    PRIVATE_ROOMS,
    REGULAR_TABLES,
    ResourceType,
    RestaurantResource,
    SeatingPreference,
    private_room_minimum_spend_for_party_size,
)


class AllocationStatus(StrEnum):
    """Availability result states for internal resource allocation."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PRIVATE_ROOM_REQUIRED = "private_room_required"
    MANAGER_REQUIRED = "manager_required"


@dataclass(frozen=True)
class ExistingReservation:
    """Existing reservation block used for local conflict checks."""

    resource_ids: tuple[str, ...]
    start: datetime
    end: datetime
    status: str = "confirmed"


@dataclass(frozen=True)
class AllocationOutcome:
    """Result of a resource allocation attempt."""

    status: AllocationStatus
    resource: RestaurantResource | None = None
    private_room_minimum_spend_krw: int | None = None
    reason: str = ""


def reservations_overlap(
    existing_start: datetime,
    existing_end: datetime,
    requested_start: datetime,
    requested_end: datetime,
) -> bool:
    """Return true when two half-open datetime intervals overlap."""
    return existing_start < requested_end and existing_end > requested_start


def _occupied_resource_ids(
    *,
    start: datetime,
    end: datetime,
    existing_reservations: list[ExistingReservation],
) -> set[str]:
    occupied: set[str] = set()
    for existing in existing_reservations:
        if existing.status == "cancelled":
            continue
        if reservations_overlap(existing.start, existing.end, start, end):
            occupied.update(existing.resource_ids)
    return occupied


def _resource_is_available(resource: RestaurantResource, occupied_resource_ids: set[str]) -> bool:
    return not set(resource.members).intersection(occupied_resource_ids)


def _sort_candidates(resources: list[RestaurantResource]) -> list[RestaurantResource]:
    return sorted(resources, key=lambda resource: (resource.capacity, not resource.is_window_side, resource.id))


def _regular_candidates(party_size: int, seating_preference: SeatingPreference) -> list[RestaurantResource]:
    candidates = []
    for resource in REGULAR_TABLES:
        if resource.capacity < party_size:
            continue
        if resource.resource_type == ResourceType.COMBINED_TABLE and party_size < 7:
            continue
        candidates.append(resource)

    if seating_preference == SeatingPreference.WINDOW_SIDE:
        candidates = [resource for resource in candidates if resource.is_window_side]

    return _sort_candidates(candidates)


def _private_room_candidates(party_size: int) -> list[RestaurantResource]:
    candidates = []
    for resource in PRIVATE_ROOMS:
        if resource.capacity < party_size:
            continue
        if resource.resource_type == ResourceType.COMBINED_PRIVATE_ROOM and party_size < 7:
            continue
        candidates.append(resource)
    return _sort_candidates(candidates)


def allocate_resource(
    *,
    party_size: int,
    seating_preference: SeatingPreference,
    start: datetime,
    end: datetime,
    existing_reservations: list[ExistingReservation],
) -> AllocationOutcome:
    if party_size < 1:
        raise ValueError("party size must be at least 1")

    if party_size > 12:
        return AllocationOutcome(
            status=AllocationStatus.MANAGER_REQUIRED,
            reason="party size is above automatic booking limit",
        )

    occupied_resource_ids = _occupied_resource_ids(
        start=start,
        end=end,
        existing_reservations=existing_reservations,
    )

    if seating_preference == SeatingPreference.PRIVATE_ROOM:
        for resource in _private_room_candidates(party_size):
            if _resource_is_available(resource, occupied_resource_ids):
                return AllocationOutcome(
                    status=AllocationStatus.AVAILABLE,
                    resource=resource,
                    private_room_minimum_spend_krw=private_room_minimum_spend_for_party_size(
                        party_size
                    ),
                )
        return AllocationOutcome(
            status=AllocationStatus.UNAVAILABLE,
            reason="no private room is available",
        )

    if party_size >= 9:
        return AllocationOutcome(
            status=AllocationStatus.PRIVATE_ROOM_REQUIRED,
            reason="regular seating is not available for 9 to 12 guests",
        )

    for resource in _regular_candidates(party_size, seating_preference):
        if _resource_is_available(resource, occupied_resource_ids):
            return AllocationOutcome(status=AllocationStatus.AVAILABLE, resource=resource)

    return AllocationOutcome(
        status=AllocationStatus.UNAVAILABLE,
        reason="no suitable regular table is available",
    )
