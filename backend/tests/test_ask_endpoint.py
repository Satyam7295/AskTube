from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import app.db.database as database_module
from app.db.base import Base
from app.main import app
from app.services.embedding_service import EmbeddingModelError
from app.services.llm_service import LLMConfigurationError
from app.services.qdrant_service import QdrantConfigurationError, QdrantSearchError
from app.services.retrieval_service import RetrievalInputError


@pytest.fixture(autouse=True)
def ask_database():
    db_url = "sqlite://"
    engine = create_engine(
        db_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    database_module.engine = engine
    database_module.SessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    yield
    engine.dispose()


def test_ask_rejects_empty_query():
    response = TestClient(app).post("/api/ask", json={"query": ""})
    assert response.status_code == 422


def test_ask_returns_503_when_qdrant_search_fails():
    with patch("app.api.ask.RetrievalService") as mock_cls:
        mock_cls.return_value.retrieve.side_effect = QdrantSearchError("Qdrant vector search failed.")
        response = TestClient(app).post("/api/ask", json={"query": "What is this video about?"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Semantic search service is unavailable."


def test_ask_returns_503_when_qdrant_not_configured():
    with patch("app.api.ask.RetrievalService") as mock_cls:
        mock_cls.return_value.retrieve.side_effect = QdrantConfigurationError("Qdrant is not configured. Set QDRANT_URL.")
        response = TestClient(app).post("/api/ask", json={"query": "What is this video about?"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Semantic search service is unavailable."


def test_ask_503_does_not_leak_collection_name():
    with patch("app.api.ask.RetrievalService") as mock_cls:
        mock_cls.return_value.retrieve.side_effect = QdrantSearchError("Collection asktube_chunks does not exist")
        response = TestClient(app).post("/api/ask", json={"query": "What is this video about?"})
    assert response.status_code == 503
    assert "asktube_chunks" not in response.text


def test_collection_missing_raises_qdrant_search_error():
    from app.core.config import Settings
    from app.services.qdrant_service import QdrantService

    class CollectionMissingClient:
        def query_points(self, **kwargs):
            raise Exception("Unexpected Response: 404 (Not Found) - Collection does not exist")

    settings = Settings(qdrant_url="https://example.qdrant.io", qdrant_collection_name="asktube_chunks", embedding_dimension=3)
    service = QdrantService(settings=settings, client=CollectionMissingClient())
    with pytest.raises(QdrantSearchError, match="Qdrant vector search failed"):
        service.search([0.1, 0.2, 0.3], limit=5)


def test_collection_missing_is_logged(caplog):
    import logging
    from app.core.config import Settings
    from app.services.qdrant_service import QdrantService

    class CollectionMissingClient:
        def query_points(self, **kwargs):
            raise Exception("Unexpected Response: 404 (Not Found) - Collection doesn't exist")

    settings = Settings(qdrant_url="https://example.qdrant.io", qdrant_collection_name="asktube_chunks", embedding_dimension=3)
    service = QdrantService(settings=settings, client=CollectionMissingClient())
    with caplog.at_level(logging.ERROR, logger="app.services.qdrant_service"):
        with pytest.raises(QdrantSearchError):
            service.search([0.1, 0.2, 0.3], limit=5)
    assert any("does not exist" in r.message for r in caplog.records)


def test_ask_returns_502_when_embedding_fails():
    with patch("app.api.ask.RetrievalService") as mock_cls:
        mock_cls.return_value.retrieve.side_effect = EmbeddingModelError("Embedding model could not be loaded.")
        response = TestClient(app).post("/api/ask", json={"query": "What is this about?"})
    assert response.status_code == 502
    assert "embedding" in response.json()["detail"].lower()


def test_ask_returns_answer_when_pipeline_succeeds():
    from app.schemas.answer import LLMAnswer
    from app.schemas.context import RetrievedSource
    from app.schemas.search import SearchResult
    fake_retrieval_result = SearchResult(
        chunk_id=1, video_id="dQw4w9WgXcQ", score=0.92,
        text="Python is a versatile programming language.",
        start_time=0.0, end_time=10.0, chunk_index=0,
        language_code="en", segment_start_index=0, segment_end_index=1,
        character_count=42, word_count=7,
    )
    # context.sources must be RetrievedSource (what AskResponse.sources expects)
    fake_source = RetrievedSource(
        chunk_id=1, video_id="dQw4w9WgXcQ", score=0.92,
        text="Python is a versatile programming language.",
        start_time=0.0, end_time=10.0, chunk_index=0,
        language_code="en", segment_start_index=0, segment_end_index=1,
        character_count=42, word_count=7,
    )
    fake_answer = LLMAnswer(
        answer="Python is a versatile programming language.",
        provider="groq", model="llama-3.3-70b-versatile", insufficient_context=False,
    )
    with patch("app.api.ask.RetrievalService") as mr, patch("app.api.ask.ContextBuilder") as mc, patch("app.api.ask.LLMService") as ml:
        mr.return_value.retrieve.return_value = ("What is Python?", [fake_retrieval_result])
        fake_ctx = MagicMock()
        fake_ctx.sources = [fake_source]
        mc.return_value.build.return_value = fake_ctx
        ml.return_value.generate_answer.return_value = fake_answer
        response = TestClient(app).post("/api/ask", json={"query": "What is Python?"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "What is Python?"
    assert "Python" in body["answer"]
    assert body["sources"][0]["chunk_id"] == 1
    assert body["insufficient_context"] is False


def test_ask_returns_503_when_llm_not_configured():
    from app.schemas.search import SearchResult
    fake_result = SearchResult(
        chunk_id=1, video_id="dQw4w9WgXcQ", score=0.88,
        text="Some relevant transcript text.",
        start_time=0.0, end_time=5.0, chunk_index=0,
        language_code="en", segment_start_index=0, segment_end_index=1,
        character_count=30, word_count=5,
    )
    with patch("app.api.ask.RetrievalService") as mr, patch("app.api.ask.ContextBuilder") as mc, patch("app.api.ask.LLMService") as ml:
        mr.return_value.retrieve.return_value = ("question?", [fake_result])
        fake_ctx = MagicMock()
        fake_ctx.sources = [fake_result]
        mc.return_value.build.return_value = fake_ctx
        ml.return_value.generate_answer.side_effect = LLMConfigurationError("Groq API key is not configured.")
        response = TestClient(app).post("/api/ask", json={"query": "What is this about?"})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "Groq" in detail or "configured" in detail.lower()
