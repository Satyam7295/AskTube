import math
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.database as database_module
from app.db.base import Base
from app.main import app
from app.repositories.transcript_repository import TranscriptRepository
from app.services.embedding_service import EmbeddingInputError, EmbeddingModelError, EmbeddingService


VIDEO_ID = "dQw4w9WgXcQ"
MODEL_NAME = "test-embedding-model"


class FakeEmbeddingModel:
    dimension = 6

    def __init__(self, calls: list[list[str]]) -> None:
        self.calls = calls

    def encode(self, texts: list[str], **kwargs) -> list[list[float]]:
        self.calls.append(texts)
        vectors = []
        for text in texts:
            lowered = text.lower()
            vector = [
                float(any(word in lowered for word in ("cat", "kitten"))),
                float(any(word in lowered for word in ("sofa", "couch"))),
                float("sitting" in lowered),
                float("sql" in lowered or "database" in lowered),
                float("structured" in lowered or "tables" in lowered),
                float(len(lowered.split()) % 3 + 1),
            ]
            if kwargs.get("normalize_embeddings"):
                length = math.sqrt(sum(value * value for value in vector))
                vector = [value / length for value in vector]
            vectors.append(vector)
        return vectors


@pytest.fixture(autouse=True)
def embedding_database() -> None:
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


def service(calls: list[list[str]] | None = None, factory=None) -> EmbeddingService:
    calls = calls if calls is not None else []
    model = FakeEmbeddingModel(calls)
    return EmbeddingService(model_name=MODEL_NAME, model=model, model_factory=factory, normalize=True)


def test_valid_text_produces_normalized_embedding() -> None:
    vector = service().embed_text("The cat is sitting on the sofa.")

    assert len(vector) == 6
    assert all(isinstance(value, float) for value in vector)
    assert math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0)


def test_empty_and_whitespace_text_are_rejected() -> None:
    embedding_service = service()

    with pytest.raises(EmbeddingInputError):
        embedding_service.embed_text("")
    with pytest.raises(EmbeddingInputError):
        embedding_service.embed_text("   \t")


def test_identical_text_is_deterministic_and_related_text_is_closer() -> None:
    embedding_service = service()
    cat = embedding_service.embed_text("The cat is sitting on the sofa.")
    same = embedding_service.embed_text("The cat is sitting on the sofa.")
    kitten = embedding_service.embed_text("The kitten is sitting on the couch.")
    sql = embedding_service.embed_text("SQL databases use structured tables.")

    assert cat == same
    related_similarity = sum(left * right for left, right in zip(cat, kitten))
    unrelated_similarity = sum(left * right for left, right in zip(cat, sql))
    assert related_similarity > unrelated_similarity


def test_batch_preserves_order_and_reuses_model() -> None:
    calls: list[list[str]] = []
    factory_calls: list[str] = []

    def factory(model_name: str) -> FakeEmbeddingModel:
        factory_calls.append(model_name)
        return FakeEmbeddingModel(calls)

    embedding_service = EmbeddingService(model_name=MODEL_NAME, model_factory=factory, batch_size=4)
    first = embedding_service.embed_texts(["first", "second"])
    second = embedding_service.embed_texts(["third"])

    assert len(first) == 2
    assert len(second) == 1
    assert calls == [["first", "second"], ["third"]]
    assert factory_calls == [MODEL_NAME]


def test_model_loading_failure_is_wrapped() -> None:
    def failing_factory(model_name: str):
        raise OSError("local model unavailable")

    with pytest.raises(EmbeddingModelError, match="could not be loaded"):
        EmbeddingService(model_name=MODEL_NAME, model_factory=failing_factory).embed_text("text")


def test_embeddings_are_persisted_with_metadata_and_are_idempotent() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    stored = repository.replace_chunks(VIDEO_ID, "en", [{
        "video_id": VIDEO_ID,
        "language_code": "en",
        "chunk_index": 0,
        "text": "The cat is sitting on the sofa.",
        "start_time": 0.0,
        "end_time": 2.0,
        "segment_start_index": 0,
        "segment_end_index": 0,
        "character_count": 33,
        "word_count": 7,
    }])
    embedding_service = service()
    generated = embedding_service.embed_chunks(stored)
    repository.save_embeddings({generated[0].chunk_id: generated[0].vector}, MODEL_NAME, 6)

    persisted = repository.get_chunks(VIDEO_ID)[0]
    assert persisted.embedding_model == MODEL_NAME
    assert persisted.embedding_dimension == 6
    assert len(EmbeddingService.decode_vector(persisted.embedding)) == 6

    with database_module.get_session_factory()() as session:
        assert session.query(type(persisted)).count() == 1


def test_different_model_metadata_is_regenerated_instead_of_reused() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    stored = repository.replace_chunks(VIDEO_ID, "en", [{
        "video_id": VIDEO_ID,
        "language_code": "en",
        "chunk_index": 0,
        "text": "model version one",
        "start_time": 0.0,
        "end_time": 1.0,
        "segment_start_index": 0,
        "segment_end_index": 0,
        "character_count": 17,
        "word_count": 3,
    }])
    repository.save_embeddings({stored[0].id: [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]}, "old-model", 6)

    current = repository.get_chunks(VIDEO_ID)[0]
    assert current.embedding_model != MODEL_NAME
    replacement = service().embed_chunks([current])[0]
    repository.save_embeddings({replacement.chunk_id: replacement.vector}, MODEL_NAME, 6)

    assert repository.get_chunks(VIDEO_ID)[0].embedding_model == MODEL_NAME


def test_embedding_endpoint_uses_stored_chunks_and_reuses_existing_vector() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.replace_chunks(VIDEO_ID, "en", [{
        "video_id": VIDEO_ID,
        "language_code": "en",
        "chunk_index": 0,
        "text": "stored text",
        "start_time": 0.0,
        "end_time": 1.0,
        "segment_start_index": 0,
        "segment_end_index": 0,
        "character_count": 11,
        "word_count": 2,
    }])
    calls: list[list[str]] = []
    fake_service = service(calls)

    with patch("app.api.videos.EmbeddingService", return_value=fake_service):
        first = TestClient(app).post(f"/api/videos/{VIDEO_ID}/embeddings")
        second = TestClient(app).post(f"/api/videos/{VIDEO_ID}/embeddings")

    assert first.status_code == 200
    assert first.json()["generated_chunks"] == 1
    assert second.status_code == 200
    assert second.json()["generated_chunks"] == 0
    assert second.json()["reused_chunks"] == 1
    assert len(calls) == 1


def test_embedding_endpoint_does_not_expose_model_errors() -> None:
    with patch("app.api.videos.TranscriptRepository.get_chunks", return_value=[SimpleNamespace(
        embedding=None,
        embedding_model=None,
        embedding_dimension=None,
        text="text",
        id=1,
        chunk_index=0,
        language_code="en",
    )]), patch("app.api.videos.EmbeddingService.embed_chunks", side_effect=EmbeddingModelError("secret path")):
        response = TestClient(app).post(f"/api/videos/{VIDEO_ID}/embeddings")

    assert response.status_code == 500
    assert response.json()["detail"] == "Embedding generation failed."
    assert "secret path" not in response.text
