from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import isfinite
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, FieldCondition, Filter, MatchValue, VectorParams
except ImportError:  # pragma: no cover - exercised only when the dependency is absent.
    QdrantClient = None  # type: ignore[assignment]
    Distance = None  # type: ignore[assignment]
    VectorParams = None  # type: ignore[assignment]
    FieldCondition = Filter = MatchValue = None  # type: ignore[assignment]


class QdrantConfigurationError(RuntimeError):
    """Raised when Qdrant is not configured correctly."""


class QdrantVectorValidationError(ValueError):
    """Raised when a vector cannot safely be stored."""


class QdrantSearchError(RuntimeError):
    """Raised when a Qdrant search cannot be completed."""


@dataclass(frozen=True)
class QdrantSearchResult:
    point_id: Any
    score: float
    payload: dict[str, Any]


class QdrantService:
    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        if not self.settings.qdrant_url:
            raise QdrantConfigurationError("Qdrant is not configured. Set QDRANT_URL in the backend environment.")
        if self.settings.qdrant_collection_name.strip() == "":
            raise QdrantConfigurationError("Qdrant collection name must not be empty.")
        if self.settings.embedding_dimension < 1:
            raise QdrantConfigurationError("Embedding dimension must be positive.")

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        if QdrantClient is None:
            raise QdrantConfigurationError("Qdrant client dependency is not installed.")
        return QdrantClient(url=self.settings.qdrant_url, api_key=self.settings.qdrant_api_key, timeout=10.0)

    def ensure_collection(self) -> Any:
        try:
            collection = self.client.get_collection(self.settings.qdrant_collection_name)
        except Exception as error:
            if isinstance(error, QdrantConfigurationError):
                raise
            collection = None

        if collection is not None:
            return collection

        if VectorParams is None or Distance is None:
            raise QdrantConfigurationError("Qdrant client dependency is not installed.")

        try:
            return self.client.create_collection(
                collection_name=self.settings.qdrant_collection_name,
                vectors_config=VectorParams(size=self.settings.embedding_dimension, distance=Distance.COSINE),
            )
        except Exception as error:
            raise QdrantConfigurationError("Qdrant collection could not be created.") from error

    def validate_vector(self, vector: Sequence[float] | None) -> list[float]:
        if not isinstance(vector, (list, tuple)) or not vector:
            raise QdrantVectorValidationError("Vector is empty or missing.")
        cleaned = [float(value) for value in vector]
        if not all(isfinite(value) for value in cleaned):
            raise QdrantVectorValidationError("Vector contains NaN or infinite values.")
        if len(cleaned) != self.settings.embedding_dimension:
            raise QdrantVectorValidationError(
                f"Vector dimension mismatch: expected {self.settings.embedding_dimension}, received {len(cleaned)}."
            )
        return cleaned

    @staticmethod
    def _point_id(chunk_id: Any) -> int:
        return int(chunk_id)

    def build_point(self, chunk: Any, vector: Sequence[float]) -> dict[str, Any]:
        payload = {
            "chunk_id": int(getattr(chunk, "id")),
            "video_id": getattr(chunk, "video_id"),
            "language_code": getattr(chunk, "language_code", "en"),
            "chunk_index": int(getattr(chunk, "chunk_index", 0)),
            "text": getattr(chunk, "text", ""),
            "start_time": float(getattr(chunk, "start_time", 0.0)),
            "end_time": float(getattr(chunk, "end_time", 0.0)),
        }

        for field_name in ("segment_start_index", "segment_end_index", "character_count", "word_count"):
            value = getattr(chunk, field_name, None)
            if value is not None:
                payload[field_name] = int(value)

        return {
            "id": self._point_id(getattr(chunk, "id")),
            "vector": list(self.validate_vector(vector)),
            "payload": payload,
        }

    def upsert_chunks(self, chunks: Iterable[Any], embeddings_by_chunk_id: dict[int | str, Sequence[float]]) -> dict[str, Any]:
        self.ensure_collection()
        points = []
        for chunk in chunks:
            chunk_id = getattr(chunk, "id")
            vector = embeddings_by_chunk_id.get(chunk_id)
            if vector is None:
                continue
            points.append(self.build_point(chunk, vector))

        if not points:
            return {"collection": self.settings.qdrant_collection_name, "upserted": 0}

        try:
            self.client.upsert(collection_name=self.settings.qdrant_collection_name, points=points)
        except Exception as error:
            raise QdrantConfigurationError("Qdrant vector upsert failed.") from error
        return {"collection": self.settings.qdrant_collection_name, "upserted": len(points)}

    def sync_chunks(self, chunks: Sequence[Any], embeddings_by_chunk_id: dict[int | str, Sequence[float]]) -> dict[str, Any]:
        total_chunks = len(chunks)
        skipped = 0
        points: list[dict[str, Any]] = []
        self.ensure_collection()

        for chunk in chunks:
            chunk_id = getattr(chunk, "id")
            vector = embeddings_by_chunk_id.get(chunk_id)
            if vector is None:
                skipped += 1
                continue
            try:
                points.append(self.build_point(chunk, vector))
            except QdrantVectorValidationError:
                skipped += 1
                continue

        if points:
            try:
                self.client.upsert(collection_name=self.settings.qdrant_collection_name, points=points)
            except Exception as error:
                raise QdrantConfigurationError("Qdrant vector upsert failed.") from error

        return {
            "collection": self.settings.qdrant_collection_name,
            "total_chunks": total_chunks,
            "upserted": len(points),
            "skipped": skipped,
        }

    def delete_vectors(self, chunk_ids: Iterable[int | str]) -> None:
        ids = [int(chunk_id) for chunk_id in chunk_ids]
        if not ids:
            return
        try:
            self.client.delete(collection_name=self.settings.qdrant_collection_name, points=ids)
        except Exception as error:
            raise QdrantConfigurationError("Qdrant vector delete failed.") from error

    def get_collection_info(self) -> Any:
        try:
            return self.client.get_collection(self.settings.qdrant_collection_name)
        except Exception as error:
            raise QdrantConfigurationError("Qdrant collection information is unavailable.") from error

    def search(
        self,
        vector: Sequence[float],
        limit: int,
        video_id: str | None = None,
        score_threshold: float | None = None,
    ) -> list[QdrantSearchResult]:
        query_vector = self.validate_vector(vector)
        if limit < 1:
            raise QdrantVectorValidationError("Search limit must be positive.")

        query_filter = None
        if video_id is not None:
            if Filter is None or FieldCondition is None or MatchValue is None:
                raise QdrantConfigurationError("Qdrant client dependency is not installed.")
            query_filter = Filter(must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))])

        try:
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.settings.qdrant_collection_name,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                )
                points = response.points
            else:
                points = self.client.search(
                    collection_name=self.settings.qdrant_collection_name,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=True,
                )
        except Exception as error:
            raise QdrantSearchError("Qdrant vector search failed.") from error

        results: list[QdrantSearchResult] = []
        for point in points or []:
            payload = getattr(point, "payload", None)
            if not isinstance(payload, dict):
                raise QdrantSearchError("Qdrant returned malformed search metadata.")
            try:
                score = float(getattr(point, "score"))
            except (TypeError, ValueError) as error:
                raise QdrantSearchError("Qdrant returned a malformed similarity score.") from error
            results.append(QdrantSearchResult(getattr(point, "id", None), score, payload))
        return results
