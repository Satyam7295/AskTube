import math
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.qdrant_service import QdrantConfigurationError, QdrantService, QdrantVectorValidationError


class FakeQdrantClient:
    def __init__(self):
        self.collections = {}
        self.upserts = []

    def get_collection(self, collection_name: str):
        return self.collections.get(collection_name)

    def create_collection(self, collection_name: str, vectors_config=None, **kwargs):
        self.collections[collection_name] = {
            "config": {"params": {"size": vectors_config.size, "distance": vectors_config.distance}},
            "points": {},
        }
        return True

    def upsert(self, collection_name: str, points, **kwargs):
        self.upserts.append({"collection": collection_name, "points": list(points)})
        current = self.collections.setdefault(collection_name, {"points": {}})
        current.setdefault("points", {})
        for point in points:
            current["points"][point["id"]] = point
        return {"result": True}

    def delete(self, collection_name: str, points=None, **kwargs):
        if points is None:
            self.collections.pop(collection_name, None)
            return {"result": True}
        current = self.collections.get(collection_name, {})
        for item in points:
            current.get("points", {}).pop(item, None)
        return {"result": True}


@pytest.fixture
def fake_client():
    return FakeQdrantClient()


def test_qdrant_configuration_accepts_local_and_cloud_settings():
    local = Settings(qdrant_url="http://localhost:6333", qdrant_api_key=None)
    cloud = Settings(qdrant_url="https://example.qdrant.io", qdrant_api_key="secret")

    assert local.qdrant_url == "http://localhost:6333"
    assert local.qdrant_api_key is None
    assert cloud.qdrant_api_key == "secret"


def test_qdrant_configuration_requires_url():
    with pytest.raises(QdrantConfigurationError, match="QDRANT_URL"):
        QdrantService(settings=Settings(qdrant_url=None, qdrant_collection_name="asktube_chunks"), client=FakeQdrantClient())


def test_collection_creation_uses_embedding_dimension_and_cosine_distance(fake_client):
    settings = Settings(qdrant_url="http://localhost:6333", qdrant_collection_name="asktube_chunks", embedding_dimension=384)
    service = QdrantService(settings=settings, client=fake_client)

    service.ensure_collection()

    collection = fake_client.collections["asktube_chunks"]
    assert collection["config"]["params"]["size"] == 384
    assert collection["config"]["params"]["distance"] == "Cosine"


def test_point_id_is_deterministic_and_payload_contains_metadata():
    settings = Settings(qdrant_url="http://localhost:6333", qdrant_collection_name="asktube_chunks", embedding_dimension=384)
    service = QdrantService(settings=settings, client=FakeQdrantClient())
    chunk = SimpleNamespace(
        id=42,
        video_id="dQw4w9WgXcQ",
        language_code="en",
        chunk_index=7,
        text="Hello world from AskTube.",
        start_time=12.5,
        end_time=18.0,
        segment_start_index=5,
        segment_end_index=8,
        character_count=24,
        word_count=5,
    )

    point = service.build_point(chunk, [0.1] * 384)

    assert point["id"] == 42
    assert point["vector"] == [0.1] * 384
    assert point["payload"]["chunk_id"] == 42
    assert point["payload"]["video_id"] == "dQw4w9WgXcQ"
    assert point["payload"]["chunk_index"] == 7
    assert point["payload"]["text"] == "Hello world from AskTube."
    assert point["payload"]["start_time"] == 12.5
    assert point["payload"]["end_time"] == 18.0


def test_vector_validation_accepts_expected_dimension_and_rejects_invalid_values():
    settings = Settings(qdrant_url="http://localhost:6333", qdrant_collection_name="asktube_chunks", embedding_dimension=384)
    service = QdrantService(settings=settings, client=FakeQdrantClient())

    assert service.validate_vector([0.0] * 384) == [0.0] * 384

    with pytest.raises(QdrantVectorValidationError, match="expected 384"):
        service.validate_vector([0.1] * 768)

    with pytest.raises(QdrantVectorValidationError, match="empty"):
        service.validate_vector([])

    with pytest.raises(QdrantVectorValidationError, match="NaN|infinite"):
        service.validate_vector([0.1, float("nan"), 0.2])


def test_upsert_is_idempotent_for_same_chunks(fake_client):
    settings = Settings(qdrant_url="http://localhost:6333", qdrant_collection_name="asktube_chunks", embedding_dimension=384)
    service = QdrantService(settings=settings, client=fake_client)
    chunk = SimpleNamespace(
        id=1,
        video_id="dQw4w9WgXcQ",
        language_code="en",
        chunk_index=0,
        text="Alpha",
        start_time=0.0,
        end_time=1.0,
        segment_start_index=0,
        segment_end_index=0,
        character_count=5,
        word_count=1,
    )

    first = service.upsert_chunks([chunk], {1: [0.5] * 384})
    second = service.upsert_chunks([chunk], {1: [0.5] * 384})

    assert first["upserted"] == 1
    assert second["upserted"] == 1
    assert len(fake_client.collections["asktube_chunks"]["points"]) == 1


def test_sync_route_uses_stored_embeddings_and_skips_invalid_missing_data():
    settings = Settings(qdrant_url="http://localhost:6333", qdrant_collection_name="asktube_chunks", embedding_dimension=384)
    fake_client = FakeQdrantClient()
    service = QdrantService(settings=settings, client=fake_client)

    chunk = SimpleNamespace(
        id=3,
        video_id="dQw4w9WgXcQ",
        language_code="en",
        chunk_index=0,
        text="Stored chunk text",
        start_time=0.0,
        end_time=2.0,
        segment_start_index=0,
        segment_end_index=0,
        character_count=18,
        word_count=3,
        embedding='[0.1, 0.2, 0.3]'
    )
    with pytest.raises(QdrantVectorValidationError):
        service.build_point(chunk, [0.5] * 768)

    result = service.sync_chunks([chunk], {4: [0.5] * 384})
    assert result["skipped"] == 1

    result = service.sync_chunks([chunk], {3: [0.5] * 384})
    assert result["upserted"] == 1
    assert result["total_chunks"] == 1

    result = service.sync_chunks([chunk], {3: [0.5] * 384})
    assert result["upserted"] == 1
    assert result["total_chunks"] == 1


def test_qdrant_client_failures_are_raised_cleanly():
    class BrokenClient:
        def get_collection(self, collection_name: str):
            raise ConnectionError("qdrant unavailable")

    settings = Settings(qdrant_url="http://localhost:6333", qdrant_collection_name="asktube_chunks", embedding_dimension=384)
    service = QdrantService(settings=settings, client=BrokenClient())

    with pytest.raises(QdrantConfigurationError):
        service.ensure_collection()
