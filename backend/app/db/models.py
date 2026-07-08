"""SQLAlchemy models for the reservation dashboard database."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.utils.time import SEOUL_TZ


def new_id() -> str:
    """Return a compact opaque primary key."""
    return uuid4().hex


def now_in_seoul() -> datetime:
    """Return the current Seoul time for audit columns."""
    return datetime.now(SEOUL_TZ)


class CustomerModel(Base):
    """Customer profile data shared by reservations and future staff APIs."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32), index=True)
    preferences: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    staff_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_in_seoul)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_in_seoul,
        onupdate=now_in_seoul,
    )

    reservations: Mapped[list[ReservationModel]] = relationship(back_populates="customer")


class RestaurantResourceModel(Base):
    """Bookable table, private room, or allowed combined resource."""

    __tablename__ = "restaurant_resources"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40), index=True)
    capacity: Mapped[int] = mapped_column(Integer)
    is_window_side: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_in_seoul)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_in_seoul,
        onupdate=now_in_seoul,
    )

    member_links: Mapped[list[ResourceMember]] = relationship(
        foreign_keys="ResourceMember.resource_id",
        cascade="all, delete-orphan",
        back_populates="resource",
    )


class ResourceMember(Base):
    """Link from an allowed combined resource to its physical resources."""

    __tablename__ = "resource_members"
    __table_args__ = (UniqueConstraint("resource_id", "member_resource_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("restaurant_resources.id"),
        index=True,
    )
    member_resource_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("restaurant_resources.id"),
        index=True,
    )

    resource: Mapped[RestaurantResourceModel] = relationship(
        foreign_keys=[resource_id],
        back_populates="member_links",
    )


class ReservationModel(Base):
    """Reservation or walk-in record stored in the database."""

    __tablename__ = "reservations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    customer_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("customers.id"),
        nullable=True,
        index=True,
    )
    customer_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32), index=True)
    party_size: Mapped[int] = mapped_column(Integer)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    seating_preference: Mapped[str] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergy_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    private_room_minimum_spend_krw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_bill_krw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="confirmed", index=True)
    source: Mapped[str] = mapped_column(String(40), default="ai_call", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_in_seoul)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_in_seoul,
        onupdate=now_in_seoul,
    )

    customer: Mapped[CustomerModel | None] = relationship(back_populates="reservations")
    resource_assignments: Mapped[list[ReservationResourceAssignment]] = relationship(
        cascade="all, delete-orphan",
        back_populates="reservation",
    )


class ReservationResourceAssignment(Base):
    """Assignment from a reservation to one or more physical resources."""

    __tablename__ = "reservation_resource_assignments"
    __table_args__ = (UniqueConstraint("reservation_id", "resource_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("reservations.id"),
        index=True,
    )
    resource_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey("restaurant_resources.id"),
        index=True,
    )

    reservation: Mapped[ReservationModel] = relationship(back_populates="resource_assignments")


class CallLogModel(Base):
    """Vapi call history for operational review."""

    __tablename__ = "call_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    call_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_in_seoul)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reservation_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("reservations.id"),
        nullable=True,
    )


class ManagerFollowupModel(Base):
    """Manager follow-up task separated from call logs."""

    __tablename__ = "manager_followups"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    customer_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text)
    party_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reservation_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_in_seoul)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_in_seoul,
        onupdate=now_in_seoul,
    )


class AuditLogModel(Base):
    """Generic staff and system audit history."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_in_seoul)


class SettingModel(Base):
    """Editable non-secret application setting."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column("setting_key", String(120), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_in_seoul,
        onupdate=now_in_seoul,
    )


class BackupRunModel(Base):
    """Manual database backup metadata."""

    __tablename__ = "backup_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    file_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_in_seoul)


MODEL_TYPES: tuple[type[Any], ...] = (
    CustomerModel,
    RestaurantResourceModel,
    ResourceMember,
    ReservationModel,
    ReservationResourceAssignment,
    CallLogModel,
    ManagerFollowupModel,
    AuditLogModel,
    SettingModel,
    BackupRunModel,
)
