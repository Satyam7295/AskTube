from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
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
    _migrate_index_status()


def _migrate_index_status() -> None:
    """Add progress columns for installations created before async indexing."""
    if engine is None:
        return
    columns = {column["name"] for column in inspect(engine).get_columns("playlist_index_status")}
    if "processed_videos" in columns:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE playlist_index_status ADD COLUMN processed_videos INTEGER NOT NULL DEFAULT 0")
        )


def get_session_factory():
    if SessionLocal is None:
        raise DatabaseConfigurationError(
            "Database is not configured. Set DATABASE_URL in the backend environment before using PostgreSQL persistence."
        )
    return SessionLocal
