"""Add staff lifecycle timestamps."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260709_0002"
down_revision: Union[str, None] = "20260708_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column("actual_seated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "reservations",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reservations", "completed_at")
    op.drop_column("reservations", "actual_seated_at")
