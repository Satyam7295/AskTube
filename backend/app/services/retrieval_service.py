from __future__ import annotations

import math
import re
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.search import SearchResult
from app.services.embedding_service import EmbeddingInputError, EmbeddingModelError, EmbeddingService
from app.services.qdrant_service import QdrantService, QdrantVectorValidationError


class RetrievalInputError(ValueError):
    """Raised when retrieval input is invalid."""


class RetrievalResultError(ValueError):
    """Raised when Qdrant returns an invalid transcript payload."""


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        qdrant_service: QdrantService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or (qdrant_service.settings if qdrant_service is not None else get_settings())
        self.embedding_service = embedding_service or EmbeddingService()
        self.qdrant_service = qdrant_service or QdrantService()

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        video_id: str | None = None,
        score_threshold: float | None = None,
    ) -> tuple[str, list[SearchResult]]:
        if not isinstance(query, str) or not query.strip():
            raise RetrievalInputError("Query must contain non-whitespace characters.")
        normalized_query = query.strip()
        resolved_top_k = self.settings.retrieval_top_k if top_k is None else top_k
        if isinstance(top_k, bool) or not isinstance(resolved_top_k, int) or resolved_top_k < 1:
            raise RetrievalInputError("top_k must be a positive integer.")
        if resolved_top_k > self.settings.retrieval_max_top_k:
            raise RetrievalInputError(f"top_k must not exceed {self.settings.retrieval_max_top_k}.")
        if video_id is not None and (not isinstance(video_id, str) or not VIDEO_ID_PATTERN.fullmatch(video_id)):
            raise RetrievalInputError("Invalid YouTube video ID.")
        if score_threshold is not None and (
            isinstance(score_threshold, bool)
            or not isinstance(score_threshold, (int, float))
            or not math.isfinite(score_threshold)
            or score_threshold < -1
            or score_threshold > 1
        ):
            raise RetrievalInputError("score_threshold must be a finite number between -1 and 1.")

        try:
            vector = self.embedding_service.embed_text(normalized_query)
            if len(vector) != self.settings.embedding_dimension or not all(math.isfinite(value) for value in vector):
                raise RetrievalInputError("Query embedding has an invalid dimension or value.")
            if self.settings.embedding_normalize:
                norm = math.sqrt(sum(value * value for value in vector))
                if norm == 0 or not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4):
                    raise RetrievalInputError("Query embedding is not normalized.")
            matches = self.qdrant_service.search(vector, resolved_top_k, video_id, score_threshold)
        except (EmbeddingInputError, QdrantVectorValidationError) as error:
            raise RetrievalInputError("Query embedding is invalid.") from error

        return normalized_query, [self._map_result(match.payload, match.score) for match in matches]

    @staticmethod
    def _map_result(payload: dict[str, Any], score: float) -> SearchResult:
        required = ("chunk_id", "video_id", "text", "start_time", "end_time", "chunk_index")
        if any(field not in payload for field in required):
            raise RetrievalResultError("Qdrant returned incomplete transcript metadata.")
        try:
            return SearchResult(
                chunk_id=int(payload["chunk_id"]),
                video_id=str(payload["video_id"]),
                score=score,
                text=str(payload["text"]),
                start_time=float(payload["start_time"]),
                end_time=float(payload["end_time"]),
                chunk_index=int(payload["chunk_index"]),
                language_code=payload.get("language_code"),
                segment_start_index=RetrievalService._optional_int(payload.get("segment_start_index")),
                segment_end_index=RetrievalService._optional_int(payload.get("segment_end_index")),
                character_count=RetrievalService._optional_int(payload.get("character_count")),
                word_count=RetrievalService._optional_int(payload.get("word_count")),
            )
        except (TypeError, ValueError) as error:
            raise RetrievalResultError("Qdrant returned malformed transcript metadata.") from error

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return None if value is None else int(value)