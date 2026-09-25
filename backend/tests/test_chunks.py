from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.database as database_module
from app.db.base import Base
from app.main import app
from app.models.chunk import TranscriptChunk
from app.models.transcript import Transcript
from app.repositories.transcript_repository import TranscriptDatabaseError, TranscriptRepository
from app.services.transcript.chunk_service import TranscriptChunkService
from app.services.transcript.chunker import ChunkingConfig, TranscriptChunker


VIDEO_ID = "dQw4w9WgXcQ"


@pytest.fixture(autouse=True)
def chunk_database() -> None:
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    database_module.engine = engine
    database_module.SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    yield
    engine.dispose()


def stored_transcript(language_code: str = "en") -> dict:
    return {
        "video_id": VIDEO_ID,
        "language_code": language_code,
        "language_name": language_code,
        "is_generated": False,
        "segments": [
            {"text": "one two", "start": 0.0, "duration": 1.25},
            {"text": "three four", "start": 4.5, "duration": 0.5},
            {"text": "five", "start": 5.0, "duration": 0.75},
        ],
    }


def test_chunks_are_persisted_with_timestamp_boundaries() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.upsert(stored_transcript())

    response = TranscriptChunkService(
        repository, TranscriptChunker(ChunkingConfig(target_words=4, overlap_words=0))
    ).get_chunks(VIDEO_ID)

    assert response.total_chunks == 2
    assert response.chunks[0].text == "one two three four"
    assert response.chunks[0].start_time == 0.0
    assert response.chunks[0].end_time == 5.0
    assert response.chunks[1].text == "five"
    with database_module.get_session_factory()() as session:
        source = session.query(Transcript).one()
        assert source.segments == stored_transcript()["segments"]
        assert session.query(TranscriptChunk).count() == 2


def test_repeated_generation_replaces_without_duplicates() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.upsert(stored_transcript())
    service = TranscriptChunkService(repository, TranscriptChunker(ChunkingConfig(target_words=4, overlap_words=0)))

    service.get_chunks(VIDEO_ID)
    service.get_chunks(VIDEO_ID)

    with database_module.get_session_factory()() as session:
        assert session.query(TranscriptChunk).count() == 2
        assert [row.chunk_index for row in session.query(TranscriptChunk).order_by(TranscriptChunk.chunk_index)] == [0, 1]


def test_language_isolation() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.upsert(stored_transcript("en"))
    repository.upsert({**stored_transcript("es"), "segments": [{"text": "hola", "start": 2.0, "duration": 1.0}]})
    service = TranscriptChunkService(repository, TranscriptChunker(ChunkingConfig(target_words=10, overlap_words=0)))

    assert service.get_chunks(VIDEO_ID, "es").chunks[0].text == "hola"
    assert service.get_chunks(VIDEO_ID, "en").chunks[0].text == "one two three four five"


def test_chunks_route_reads_stored_transcript_without_provider_call() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.upsert(stored_transcript())

    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        response = TestClient(app).get(f"/api/videos/{VIDEO_ID}/chunks")

    assert response.status_code == 200
    assert response.json()["total_chunks"] == 1
    assert response.json()["chunks"][0]["start_time"] == 0.0
    api.return_value.list.assert_not_called()


def test_missing_transcript_returns_not_found() -> None:
    response = TestClient(app).get(f"/api/videos/{VIDEO_ID}/chunks")

    assert response.status_code == 404


def test_chunk_persistence_failure_is_wrapped() -> None:
    class BrokenRepository:
        def get(self, video_id: str, language: str | None = None):
            return type("Stored", (), {"video_id": video_id, "language_code": "en", "segments": []})()

        def replace_chunks(self, video_id: str, language_code: str, chunks: list[dict]):
            raise TranscriptDatabaseError("database unavailable")

    with pytest.raises(TranscriptDatabaseError):
        TranscriptChunkService(BrokenRepository()).get_chunks(VIDEO_ID)