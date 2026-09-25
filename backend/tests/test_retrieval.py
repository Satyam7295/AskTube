import math
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantSearchError, QdrantService
from app.services.retrieval_service import RetrievalInputError, RetrievalResultError, RetrievalService


class FakeEmbeddingModel:
    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            lowered = text.lower()
            vector = [
                float("react" in lowered or "interface" in lowered),
                float("javascript" in lowered or "frontend" in lowered),
                float("database" in lowered or "postgresql" in lowered),
            ] + [0.0] * 381
            length = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / length for value in vector])
        return vectors


class FakeQdrantClient:
    def __init__(self, points):
        self.points = points
        self.last_filter = None

    def search(self, collection_name, query_vector, query_filter, limit, score_threshold, with_payload):
        self.last_filter = query_filter
        candidates = self.points
        if query_filter is not None:
            video_id = query_filter.must[0].match.value
            candidates = [point for point in candidates if point.payload["video_id"] == video_id]
        scored = []
        for point in candidates:
            score = sum(left * right for left, right in zip(query_vector, point.vector))
            if score_threshold is None or score >= score_threshold:
                scored.append(SimpleNamespace(id=point.id, score=score, payload=point.payload))
        return sorted(scored, key=lambda point: point.score, reverse=True)[:limit]


def make_service(points):
    settings = Settings(
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_chunks",
        embedding_dimension=384,
        retrieval_top_k=5,
        retrieval_max_top_k=10,
    )
    client = FakeQdrantClient(points)
    embedding = EmbeddingService(model_name="test", model=FakeEmbeddingModel(), normalize=True)
    qdrant = QdrantService(settings=settings, client=client)
    return RetrievalService(embedding, qdrant), client


def point(point_id, video_id, text):
    embedding = EmbeddingService(model_name="test", model=FakeEmbeddingModel(), normalize=True).embed_text(text)
    return SimpleNamespace(
        id=point_id,
        vector=embedding,
        payload={
            "chunk_id": point_id,
            "video_id": video_id,
            "language_code": "en",
            "chunk_index": point_id,
            "text": text,
            "start_time": float(point_id),
            "end_time": float(point_id + 1),
            "segment_start_index": 0,
            "segment_end_index": 1,
            "character_count": len(text),
            "word_count": len(text.split()),
        },
    )


VIDEO_A = "dQw4w9WgXcQ"
VIDEO_B = "jNQXAC9IVRw"


@pytest.fixture
def retrieval():
    return make_service([
        point(1, VIDEO_A, "React is a JavaScript library for interfaces."),
        point(2, VIDEO_B, "React components build frontend interfaces."),
        point(3, VIDEO_A, "PostgreSQL is a relational database."),
    ])


def test_query_validation_and_normalization(retrieval):
    service, _ = retrieval
    query, results = service.retrieve("  What is React used for?  ")
    assert query == "What is React used for?"
    assert len(results) == 3

    for invalid in (None, "", "  ", 123):
        with pytest.raises(RetrievalInputError):
            service.retrieve(invalid)


def test_top_k_and_video_filter_are_applied_by_qdrant(retrieval):
    service, client = retrieval
    _, results = service.retrieve("What is React used for?", top_k=1, video_id=VIDEO_A)

    assert len(results) == 1
    assert results[0].video_id == VIDEO_A
    assert client.last_filter.must[0].key == "video_id"
    assert client.last_filter.must[0].match.value == VIDEO_A

    with pytest.raises(RetrievalInputError):
        service.retrieve("question", top_k=0)
    with pytest.raises(RetrievalInputError):
        service.retrieve("question", top_k=-1)
    with pytest.raises(RetrievalInputError):
        service.retrieve("question", top_k=11)


def test_results_are_ranked_and_thresholded(retrieval):
    service, _ = retrieval
    _, results = service.retrieve("What is React used for?", score_threshold=0.6)

    assert [result.chunk_id for result in results] == [1, 2]
    assert results[0].score >= results[1].score
    assert results[0].start_time == 1.0
    assert results[0].word_count == 7

    _, empty = service.retrieve("What is React used for?", score_threshold=1.0)
    assert empty == []


def test_invalid_video_id_threshold_and_malformed_payload_are_rejected(retrieval):
    service, _ = retrieval
    with pytest.raises(RetrievalInputError):
        service.retrieve("question", video_id="invalid")
    with pytest.raises(RetrievalInputError):
        service.retrieve("question", score_threshold=2)

    malformed = make_service([SimpleNamespace(id=1, vector=[1.0] + [0.0] * 383, payload={})])[0]
    with pytest.raises(RetrievalResultError):
        malformed.retrieve("React")


def test_qdrant_failure_is_not_confused_with_empty_results():
    class BrokenClient:
        def search(self, **kwargs):
            raise ConnectionError("secret connection details")

    settings = Settings(qdrant_url="http://localhost:6333", embedding_dimension=384)
    service = RetrievalService(
        EmbeddingService(model_name="test", model=FakeEmbeddingModel(), normalize=True),
        QdrantService(settings=settings, client=BrokenClient()),
    )

    with pytest.raises(QdrantSearchError):
        service.retrieve("React")