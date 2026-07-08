"""Alembic migration smoke test."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_head_creates_phase_one_tables(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration-smoke.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    config = Config("alembic.ini")
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)

    assert {
        "customers",
        "restaurant_resources",
        "resource_members",
        "reservations",
        "reservation_resource_assignments",
        "call_logs",
        "manager_followups",
        "audit_logs",
        "settings",
        "backup_runs",
    }.issubset(set(inspector.get_table_names()))
