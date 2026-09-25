from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.database as database_module
from app.main import app
from app.db.base import Base
from app.models.transcript import Transcript
from app.repositories.transcript_repository import TranscriptDatabaseError, TranscriptRepository
from app.services.transcript.transcript_service import TranscriptService


VIDEO_ID = "dQw4w9WgXcQ"


@pytest.fixture(autouse=True)
def transcript_database() -> None:
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    database_module.engine = engine
    database_module.SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    yield
    engine.dispose()


class FakeTranscript:
    def __init__(self, language_code: str, is_generated: bool, snippets: list[dict]) -> None:
        self.language_code = language_code
        self.is_generated = is_generated
        self._snippets = snippets

    def fetch(self) -> SimpleNamespace:
        return SimpleNamespace(snippets=[SimpleNamespace(**snippet) for snippet in self._snippets])


def client() -> TestClient:
    return TestClient(app)


def test_successful_transcript_preserves_response_fields() -> None:
    transcript = FakeTranscript("en", False, [
        {"text": " Welcome   to the lecture. ", "start": 0.0, "duration": 3.2},
        {"text": "Today we will discuss binary search.", "start": 3.2, "duration": 5.4},
    ])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.return_value = [transcript]
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 200
    assert response.json() == {
        "video_id": VIDEO_ID,
        "language": "en",
        "is_generated": False,
        "segments": [
            {"text": "Welcome to the lecture.", "start": 0.0, "duration": 3.2},
            {"text": "Today we will discuss binary search.", "start": 3.2, "duration": 5.4},
        ],
        "total_segments": 2,
    }


def test_fractional_timestamps_are_not_rounded() -> None:
    transcript = FakeTranscript("en", True, [{"text": "A point in time", "start": 12.43, "duration": 15.38}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.return_value = [transcript]
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.json()["segments"] == [{"text": "A point in time", "start": 12.43, "duration": 15.38}]


def test_no_transcript_returns_not_found() -> None:
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.return_value = []
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 404
    assert response.json()["detail"] == "Transcript is not available for this video."


def test_video_unavailable_returns_not_found() -> None:
    unavailable = type("VideoUnavailable", (Exception,), {})
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.side_effect = unavailable()
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 404
    assert response.json()["detail"] == "Video was not found or is unavailable."


def test_provider_failure_returns_bad_gateway() -> None:
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.side_effect = RuntimeError("provider down")
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 502
    assert response.json()["detail"] == "Transcript provider request failed."


def test_invalid_video_id_returns_validation_error() -> None:
    response = client().get("/api/videos/too-short/transcript")

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid YouTube video ID."


def test_language_selection_is_deterministic() -> None:
    spanish = FakeTranscript("es", False, [{"text": "Hola", "start": 0.0, "duration": 1.0}])
    english = FakeTranscript("en", True, [{"text": "Hello", "start": 0.0, "duration": 1.0}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.return_value = [spanish, english]
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")
        requested = client().get(f"/api/videos/{VIDEO_ID}/transcript?language=es")

    assert response.json()["language"] == "en"
    assert requested.json()["language"] == "es"


def test_service_rejects_invalid_video_id() -> None:
    with pytest.raises(ValueError, match="Invalid YouTube video ID"):
        TranscriptService(transcript_api=object()).get_transcript("invalid")


def test_transcript_is_persisted_with_timing_and_metadata() -> None:
    transcript = FakeTranscript("en", True, [{"text": "Stored", "start": 12.43, "duration": 15.38}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.return_value = [transcript]
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 200
    with database_module.get_session_factory()() as session:
        stored = session.query(Transcript).one()
        assert stored.video_id == VIDEO_ID
        assert stored.language_code == "en"
        assert stored.is_generated is True
        assert stored.segments == [{"text": "Stored", "start": 12.43, "duration": 15.38}]


def test_stored_transcript_is_returned_without_calling_provider() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.upsert(
        {
            "video_id": VIDEO_ID,
            "language_code": "es",
            "language_name": "Spanish",
            "is_generated": False,
            "segments": [{"text": "Hola", "start": 4.25, "duration": 1.75}],
        }
    )

    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript?language=es")

    assert response.status_code == 200
    assert response.json()["segments"] == [{"text": "Hola", "start": 4.25, "duration": 1.75}]
    assert response.json()["language"] == "es"
    assert response.json()["is_generated"] is False
    api.return_value.list.assert_not_called()


def test_repeated_request_does_not_create_duplicate_transcripts() -> None:
    transcript = FakeTranscript("en", False, [{"text": "Once", "start": 0.0, "duration": 1.0}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.return_value = [transcript]
        client().get(f"/api/videos/{VIDEO_ID}/transcript")
        client().get(f"/api/videos/{VIDEO_ID}/transcript")

    with database_module.get_session_factory()() as session:
        assert session.query(Transcript).count() == 1
    api.return_value.list.assert_called_once_with(VIDEO_ID)


def test_database_failure_returns_controlled_server_error() -> None:
    class BrokenRepository:
        def get(self, video_id: str, language: str | None = None):
            raise TranscriptDatabaseError("database unavailable")

    with pytest.raises(TranscriptDatabaseError):
        TranscriptService(transcript_api=object(), transcript_repository=BrokenRepository()).get_transcript(VIDEO_ID)


def test_database_failure_route_does_not_expose_internal_error() -> None:
    service = TranscriptService(
        transcript_api=object(),
        transcript_repository=type(
            "BrokenRepository",
            (),
            {"get": lambda self, video_id, language=None: (_ for _ in ()).throw(TranscriptDatabaseError("secret"))},
        )(),
    )
    with patch("app.api.videos.TranscriptService", return_value=service):
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 500
    assert response.json()["detail"] == "Transcript persistence failed."
    assert "secret" not in response.text