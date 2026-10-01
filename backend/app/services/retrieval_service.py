from __future__ import annotations

import math
import re
from typing import Any

from app.core.config import Settings, get_settings
from app.repositories.playlist_repository import PlaylistRepository
from app.schemas.search import SearchResult
from app.services.embedding_service import EmbeddingInputError, EmbeddingService
from app.services.qdrant_service import QdrantService, QdrantVectorValidationError


class RetrievalInputError(ValueError):
    """Raised when retrieval input is invalid."""


class RetrievalResultError(ValueError):
    """Raised when Qdrant returns an invalid transcript payload."""


VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
PLAYLIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
TITLE_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]+")


class RetrievalService:
    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        qdrant_service: QdrantService | None = None,
        settings: Settings | None = None,
        playlist_repository: PlaylistRepository | None = None,
    ) -> None:
        self.settings = settings or (qdrant_service.settings if qdrant_service is not None else get_settings())
        self.embedding_service = embedding_service or EmbeddingService()
        self.qdrant_service = qdrant_service or QdrantService()
        self.playlist_repository = playlist_repository

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        video_id: str | None = None,
        score_threshold: float | None = None,
        playlist_id: str | None = None,
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
        if playlist_id is not None and (
            not isinstance(playlist_id, str) or not playlist_id.strip() or not PLAYLIST_ID_PATTERN.fullmatch(playlist_id)
        ):
            raise RetrievalInputError("Invalid YouTube playlist ID.")
        if score_threshold is not None and (
            isinstance(score_threshold, bool)
            or not isinstance(score_threshold, (int, float))
            or not math.isfinite(score_threshold)
            or score_threshold < -1
            or score_threshold > 1
        ):
            raise RetrievalInputError("score_threshold must be a finite number between -1 and 1.")

        # Exact playlist-title queries must resolve to the titled video before
        # semantic search. Titles are metadata and may never occur verbatim in a
        # transcript, so embedding the title alone can otherwise select another video.
        resolved_video_id = video_id
        if resolved_video_id is None and playlist_id is not None:
            resolved_video_id = self._resolve_exact_title_video(normalized_query, playlist_id)

        try:
            vector = self.embedding_service.embed_text(normalized_query)
            if len(vector) != self.settings.embedding_dimension or not all(math.isfinite(value) for value in vector):
                raise RetrievalInputError("Query embedding has an invalid dimension or value.")
            if self.settings.embedding_normalize:
                norm = math.sqrt(sum(value * value for value in vector))
                if norm == 0 or not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4):
                    raise RetrievalInputError("Query embedding is not normalized.")
            matches = self.qdrant_service.search(
                vector,
                resolved_top_k,
                resolved_video_id,
                score_threshold,
                playlist_id,
            )
        except (EmbeddingInputError, QdrantVectorValidationError) as error:
            raise RetrievalInputError("Query embedding is invalid.") from error

        return normalized_query, [self._map_result(match.payload, match.score) for match in matches]

    def _resolve_exact_title_video(self, query: str, playlist_id: str) -> str | None:
        """Resolve an exact video-title query inside the active playlist.

        This lookup is best-effort; normal semantic retrieval remains the fallback
        if the database is unavailable or there is no exact title match.
        """
        try:
            repository = self.playlist_repository or PlaylistRepository()
            normalized_query = self._normalize_title(query)
            if not normalized_query:
                return None
            for video in repository.get_playlist_videos(playlist_id):
                title = getattr(video, "title", None)
                candidate_video_id = getattr(video, "video_id", None)
                if (
                    isinstance(title, str)
                    and isinstance(candidate_video_id, str)
                    and self._normalize_title(title) == normalized_query
                ):
                    return candidate_video_id
        except Exception:
            return None
        return None

    @staticmethod
    def _normalize_title(value: str) -> str:
        return " ".join(TITLE_NORMALIZE_PATTERN.sub(" ", value.lower()).split())

    @staticmethod
    def _map_result(payload: dict[str, Any], score: float) -> SearchResult:
        required = ("chunk_id", "video_id", "text", "start_time", "end_time", "chunk_index")
        if any(field not in payload for field in required):
            raise RetrievalResultError("Qdrant returned incomplete transcript metadata.")
        try:
            return SearchResult(
                chunk_id=int(payload["chunk_id"]),
                video_id=str(payload["video_id"]),
                playlist_id=payload.get("playlist_id"),
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
