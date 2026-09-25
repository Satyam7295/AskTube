from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import DatabaseConfigurationError, get_session_factory
from app.models.chunk import TranscriptChunk
from app.models.transcript import Transcript


class TranscriptDatabaseError(Exception):
    """Raised when transcript persistence cannot complete."""


class TranscriptRepository:
    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self._session_factory = session_factory

    @property
    def session_factory(self) -> Callable[[], Session]:
        return self._session_factory or get_session_factory()

    def get(self, video_id: str, language_code: str | None = None) -> Transcript | None:
        try:
            with self.session_factory() as session:
                query = session.query(Transcript).filter(Transcript.video_id == video_id)
                if language_code:
                    return query.filter(Transcript.language_code == language_code).one_or_none()
                return query.order_by((Transcript.language_code == "en").desc(), Transcript.id.asc()).first()
        except (DatabaseConfigurationError, SQLAlchemyError) as error:
            raise TranscriptDatabaseError("Transcript database read failed.") from error

    def upsert(self, payload: dict) -> Transcript:
        try:
            with self.session_factory() as session:
                with session.begin():
                    transcript = (
                        session.query(Transcript)
                        .filter(
                            Transcript.video_id == payload["video_id"],
                            Transcript.language_code == payload["language_code"],
                        )
                        .one_or_none()
                    )
                    if transcript is None:
                        transcript = Transcript(**payload)
                        session.add(transcript)
                    else:
                        transcript.language_name = payload.get("language_name")
                        transcript.is_generated = payload["is_generated"]
                        transcript.segments = payload["segments"]
                        transcript.updated_at = datetime.utcnow()
                    session.flush()
                    return transcript
        except (DatabaseConfigurationError, SQLAlchemyError) as error:
            raise TranscriptDatabaseError("Transcript database write failed.") from error

    def replace_chunks(self, video_id: str, language_code: str, chunks: list[dict]) -> list[TranscriptChunk]:
        try:
            with self.session_factory() as session:
                with session.begin():
                    session.query(TranscriptChunk).filter(
                        TranscriptChunk.video_id == video_id,
                        TranscriptChunk.language_code == language_code,
                    ).delete(synchronize_session=False)
                    stored = [TranscriptChunk(**chunk) for chunk in chunks]
                    session.add_all(stored)
                    session.flush()
                    return stored
        except (DatabaseConfigurationError, SQLAlchemyError) as error:
            raise TranscriptDatabaseError("Transcript chunk persistence failed.") from error

    def get_chunks(self, video_id: str, language_code: str | None = None) -> list[TranscriptChunk]:
        try:
            with self.session_factory() as session:
                query = session.query(TranscriptChunk).filter(TranscriptChunk.video_id == video_id)
                if language_code:
                    query = query.filter(TranscriptChunk.language_code == language_code)
                else:
                    query = query.filter(TranscriptChunk.language_code == "en")
                return query.order_by(TranscriptChunk.chunk_index.asc()).all()
        except (DatabaseConfigurationError, SQLAlchemyError) as error:
            raise TranscriptDatabaseError("Transcript chunk read failed.") from error