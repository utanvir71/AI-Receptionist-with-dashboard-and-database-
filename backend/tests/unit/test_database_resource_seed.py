"""Database resource seed behavior."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.models import ResourceMember, RestaurantResourceModel
from app.db.seed import seed_restaurant_resources
from app.db.session import Base


def test_resource_seed_creates_fixed_resources_and_allowed_combinations_once() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_restaurant_resources(session)
        seed_restaurant_resources(session)

        resources = {
            resource.id: resource
            for resource in session.scalars(select(RestaurantResourceModel)).all()
        }
        members = session.scalars(select(ResourceMember)).all()

    assert len(resources) == 21
    assert resources["table_1"].label == "Table 1"
    assert resources["table_1"].capacity == 3
    assert resources["tables_1_2"].capacity == 8
    assert resources["rooms_1_2"].capacity == 12

    grouped_members: dict[str, set[str]] = {}
    for member in members:
        grouped_members.setdefault(member.resource_id, set()).add(member.member_resource_id)

    assert grouped_members["tables_1_2"] == {"table_1", "table_2"}
    assert grouped_members["rooms_1_2"] == {"room_1", "room_2"}
    assert set(grouped_members) == {"tables_1_2", "rooms_1_2"}
