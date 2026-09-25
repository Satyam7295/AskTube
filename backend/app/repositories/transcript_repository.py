from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import DatabaseConfigurationError, get_session_factory
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