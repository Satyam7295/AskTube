from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import Base

# Import every mapped model before SQLAlchemy configures relationships.
from app.models import chunk, indexing, playlist, transcript, video  # noqa: F401

DATABASE_CONNECT_TIMEOUT_SECONDS = 10
DATABASE_STATEMENT_TIMEOUT_MILLISECONDS = 15000
DATABASE_LOCK_TIMEOUT_MILLISECONDS = 5000


def _engine_options(database_url: str) -> dict:
    if database_url.startswith(("postgresql://", "postgresql+")):
        return {
            "connect_args": {
                "connect_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS,
                "options": (
                    f"-c statement_timeout={DATABASE_STATEMENT_TIMEOUT_MILLISECONDS} "
                    f"-c lock_timeout={DATABASE_LOCK_TIMEOUT_MILLISECONDS}"
                ),
            },
            "pool_timeout": DATABASE_CONNECT_TIMEOUT_SECONDS,
        }
    return {}


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
    database_url = get_database_url()
    return create_engine(database_url, pool_pre_ping=True, future=True, **_engine_options(database_url))


engine = None
SessionLocal = None

try:
    database_url = get_database_url()
    engine = create_engine(database_url, pool_pre_ping=True, future=True, **_engine_options(database_url))
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
    with engine.begin() as connection:
        if "processed_videos" not in columns:
            connection.execute(text("ALTER TABLE playlist_index_status ADD COLUMN processed_videos INTEGER NOT NULL DEFAULT 0"))
        if "video_diagnostics" not in columns:
            connection.execute(text("ALTER TABLE playlist_index_status ADD COLUMN video_diagnostics JSON NOT NULL DEFAULT '[]'"))


def get_session_factory():
    if SessionLocal is None:
        raise DatabaseConfigurationError(
            "Database is not configured. Set DATABASE_URL in the backend environment before using PostgreSQL persistence."
        )
    return SessionLocal
