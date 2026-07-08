"""Initial database foundation."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260708_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("preferences", sa.Text(), nullable=True),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("staff_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_phone", "customers", ["phone"])

    op.create_table(
        "restaurant_resources",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_window_side", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_restaurant_resources_resource_type", "restaurant_resources", ["resource_type"])

    op.create_table(
        "resource_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resource_id", sa.String(length=40), nullable=False),
        sa.Column("member_resource_id", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["member_resource_id"], ["restaurant_resources.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["restaurant_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resource_id", "member_resource_id"),
    )
    op.create_index("ix_resource_members_member_resource_id", "resource_members", ["member_resource_id"])
    op.create_index("ix_resource_members_resource_id", "resource_members", ["resource_id"])

    op.create_table(
        "reservations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=True),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seating_preference", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("allergy_notes", sa.Text(), nullable=True),
        sa.Column("call_id", sa.String(length=120), nullable=True),
        sa.Column("private_room_minimum_spend_krw", sa.Integer(), nullable=True),
        sa.Column("final_bill_krw", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservations_call_id", "reservations", ["call_id"])
    op.create_index("ix_reservations_customer_id", "reservations", ["customer_id"])
    op.create_index("ix_reservations_end_at", "reservations", ["end_at"])
    op.create_index("ix_reservations_phone", "reservations", ["phone"])
    op.create_index("ix_reservations_source", "reservations", ["source"])
    op.create_index("ix_reservations_start_at", "reservations", ["start_at"])
    op.create_index("ix_reservations_status", "reservations", ["status"])

    op.create_table(
        "reservation_resource_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reservation_id", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["restaurant_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_id", "resource_id"),
    )
    op.create_index(
        "ix_reservation_resource_assignments_reservation_id",
        "reservation_resource_assignments",
        ["reservation_id"],
    )
    op.create_index(
        "ix_reservation_resource_assignments_resource_id",
        "reservation_resource_assignments",
        ["resource_id"],
    )

    op.create_table(
        "call_logs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("call_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("action_taken", sa.String(length=120), nullable=True),
        sa.Column("reservation_id", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_logs_customer_phone", "call_logs", ["customer_phone"])

    op.create_table(
        "manager_followups",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("customer_name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=True),
        sa.Column("reservation_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manager_followups_phone", "manager_followups", ["phone"])
    op.create_index("ix_manager_followups_status", "manager_followups", ["status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=80), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])

    op.create_table(
        "settings",
        sa.Column("setting_key", sa.String(length=120), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("setting_key"),
    )

    op.create_table(
        "backup_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("backup_runs")
    op.drop_table("settings")
    op.drop_index("ix_audit_logs_entity_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_manager_followups_status", table_name="manager_followups")
    op.drop_index("ix_manager_followups_phone", table_name="manager_followups")
    op.drop_table("manager_followups")
    op.drop_index("ix_call_logs_customer_phone", table_name="call_logs")
    op.drop_table("call_logs")
    op.drop_index(
        "ix_reservation_resource_assignments_resource_id",
        table_name="reservation_resource_assignments",
    )
    op.drop_index(
        "ix_reservation_resource_assignments_reservation_id",
        table_name="reservation_resource_assignments",
    )
    op.drop_table("reservation_resource_assignments")
    op.drop_index("ix_reservations_status", table_name="reservations")
    op.drop_index("ix_reservations_start_at", table_name="reservations")
    op.drop_index("ix_reservations_source", table_name="reservations")
    op.drop_index("ix_reservations_phone", table_name="reservations")
    op.drop_index("ix_reservations_end_at", table_name="reservations")
    op.drop_index("ix_reservations_customer_id", table_name="reservations")
    op.drop_index("ix_reservations_call_id", table_name="reservations")
    op.drop_table("reservations")
    op.drop_index("ix_resource_members_resource_id", table_name="resource_members")
    op.drop_index("ix_resource_members_member_resource_id", table_name="resource_members")
    op.drop_table("resource_members")
    op.drop_index("ix_restaurant_resources_resource_type", table_name="restaurant_resources")
    op.drop_table("restaurant_resources")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_table("customers")
