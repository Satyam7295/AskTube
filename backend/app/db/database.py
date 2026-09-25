from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import Base


class DatabaseConfigurationError(RuntimeError):
    pass


def get_database_url() -> str:
    settings = get_settings()
    if not settings.database_url:
        raise DatabaseConfigurationError(
            "Database is not configured. Set DATABASE_URL in the backend environment before using PostgreSQL persistence."
        )
    return settings.database_url


def get_engine() -> Engine:
    return create_engine(get_database_url(), pool_pre_ping=True, future=True)


engine = None
SessionLocal = None

try:
    database_url = get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
except DatabaseConfigurationError:
    engine = None
    SessionLocal = None


def init_db() -> None:
    if engine is None:
        raise DatabaseConfigurationError(
            "Database is not configured. Set DATABASE_URL in the backend environment before using PostgreSQL persistence."
        )
    Base.metadata.create_all(bind=engine)


def get_session_factory():
    if SessionLocal is None:
        raise DatabaseConfigurationError(
            "Database is not configured. Set DATABASE_URL in the backend environment before using PostgreSQL persistence."
        )
    return SessionLocal
