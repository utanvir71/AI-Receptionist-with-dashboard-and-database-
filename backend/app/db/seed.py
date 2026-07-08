"""Database seed helpers for fixed restaurant data."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ResourceMember, RestaurantResourceModel
from app.models.resources import PRIVATE_ROOMS, REGULAR_TABLES, RestaurantResource


FIXED_RESOURCES: tuple[RestaurantResource, ...] = (*REGULAR_TABLES, *PRIVATE_ROOMS)


def seed_restaurant_resources(session: Session) -> None:
    """Create or update the fixed tables, rooms, and allowed combined resources."""
    for resource in FIXED_RESOURCES:
        existing = session.get(RestaurantResourceModel, resource.id)
        if existing is None:
            existing = RestaurantResourceModel(id=resource.id)
            session.add(existing)

        existing.label = resource.label
        existing.resource_type = resource.resource_type.value
        existing.capacity = resource.capacity
        existing.is_window_side = resource.is_window_side
        existing.is_active = True

    session.flush()
    combined_resource_ids = [resource.id for resource in FIXED_RESOURCES if len(resource.members) > 1]
    if combined_resource_ids:
        session.execute(
            delete(ResourceMember).where(ResourceMember.resource_id.in_(combined_resource_ids))
        )

    for resource in FIXED_RESOURCES:
        if len(resource.members) <= 1:
            continue
        for member_resource_id in resource.members:
            session.add(
                ResourceMember(
                    resource_id=resource.id,
                    member_resource_id=member_resource_id,
                )
            )

    session.commit()


def get_seeded_resource_ids(session: Session) -> set[str]:
    """Return resource ids currently present in the database."""
    return set(session.scalars(select(RestaurantResourceModel.id)).all())
