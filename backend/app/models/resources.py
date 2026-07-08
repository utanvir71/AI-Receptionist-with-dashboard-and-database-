"""Restaurant table and private-room resource definitions."""

from dataclasses import dataclass
from enum import StrEnum


class SeatingPreference(StrEnum):
    """Caller seating preference values."""

    WINDOW_SIDE = "window_side"
    PRIVATE_ROOM = "private_room"
    NO_PREFERENCE = "no_preference"
    GENERAL_NOTE = "general_note"


class ResourceType(StrEnum):
    """Internal restaurant resource categories."""

    REGULAR_TABLE = "regular_table"
    COMBINED_TABLE = "combined_table"
    PRIVATE_ROOM = "private_room"
    COMBINED_PRIVATE_ROOM = "combined_private_room"


@dataclass(frozen=True)
class RestaurantResource:
    """A bookable physical restaurant resource."""

    id: str
    label: str
    resource_type: ResourceType
    capacity: int
    is_window_side: bool = False
    members: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.members:
            object.__setattr__(self, "members", (self.id,))


REGULAR_TABLES: tuple[RestaurantResource, ...] = (
    RestaurantResource("table_1", "Table 1", ResourceType.REGULAR_TABLE, 3, True),
    RestaurantResource("table_2", "Table 2", ResourceType.REGULAR_TABLE, 3, True),
    RestaurantResource("table_3", "Table 3", ResourceType.REGULAR_TABLE, 4, True),
    RestaurantResource("table_4", "Table 4", ResourceType.REGULAR_TABLE, 4, True),
    RestaurantResource("table_5", "Table 5", ResourceType.REGULAR_TABLE, 3, True),
    RestaurantResource("table_6", "Table 6", ResourceType.REGULAR_TABLE, 3, True),
    RestaurantResource("table_7", "Table 7", ResourceType.REGULAR_TABLE, 6, True),
    RestaurantResource("table_10", "Table 10", ResourceType.REGULAR_TABLE, 6),
    RestaurantResource("table_11", "Table 11", ResourceType.REGULAR_TABLE, 6),
    RestaurantResource("table_12", "Table 12", ResourceType.REGULAR_TABLE, 6),
    RestaurantResource("table_13", "Table 13", ResourceType.REGULAR_TABLE, 3),
    RestaurantResource("table_14", "Table 14", ResourceType.REGULAR_TABLE, 3),
    RestaurantResource("table_15", "Table 15", ResourceType.REGULAR_TABLE, 4),
    RestaurantResource("table_16", "Table 16", ResourceType.REGULAR_TABLE, 4),
    RestaurantResource(
        "tables_1_2",
        "Table 1 + Table 2",
        ResourceType.COMBINED_TABLE,
        8,
        True,
        ("table_1", "table_2"),
    ),
)


PRIVATE_ROOMS: tuple[RestaurantResource, ...] = (
    RestaurantResource("room_1", "Room 1", ResourceType.PRIVATE_ROOM, 6),
    RestaurantResource("room_2", "Room 2", ResourceType.PRIVATE_ROOM, 6),
    RestaurantResource("room_3", "Room 3", ResourceType.PRIVATE_ROOM, 6),
    RestaurantResource("room_4", "Room 4", ResourceType.PRIVATE_ROOM, 5),
    RestaurantResource("room_5", "Room 5", ResourceType.PRIVATE_ROOM, 6, True),
    RestaurantResource(
        "rooms_1_2",
        "Room 1 + Room 2",
        ResourceType.COMBINED_PRIVATE_ROOM,
        12,
        False,
        ("room_1", "room_2"),
    ),
)


def private_room_minimum_spend_for_party_size(party_size: int) -> int:
    """Return the private-room minimum spend in Korean won for a party size."""
    if not 1 <= party_size <= 12:
        raise ValueError("private-room party size must be between 1 and 12")

    if party_size <= 6:
        return 320_000
    if party_size <= 8:
        return 420_000
    return 620_000
