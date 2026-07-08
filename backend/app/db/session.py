"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def _is_sqlite_memory_url(database_url: str) -> bool:
    return database_url in {
        "sqlite://",
        "sqlite:///:memory:",
        "sqlite+pysqlite:///:memory:",
    }


@lru_cache
def get_engine(database_url: str) -> Engine:
    """Return a cached SQLAlchemy engine for the configured database URL."""
    connect_args: dict[str, object] = {}
    engine_options: dict[str, object] = {"pool_pre_ping": True}

    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if _is_sqlite_memory_url(database_url):
            engine_options["poolclass"] = StaticPool

    return create_engine(database_url, connect_args=connect_args, **engine_options)


@lru_cache
def get_session_factory(database_url: str) -> sessionmaker:
    """Return a cached SQLAlchemy session factory."""
    return sessionmaker(bind=get_engine(database_url), expire_on_commit=False)
