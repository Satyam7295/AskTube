from __future__ import annotations

import math
from collections import OrderedDict
from typing import Any, Iterable

from app.core.config import Settings, get_settings
from app.schemas.context import RAGContext, RetrievedSource
from app.schemas.search import SearchResult


class ContextBuilderInputError(ValueError):
    """Raised when retrieved data cannot be used to build context."""


class ContextBuilder:
    """Convert application retrieval results into bounded, traceable RAG context.

    Video groups retain their best-result relevance order. Chunks within each
    group are chronological so related transcript passages read coherently.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if self.settings.rag_max_context_chars < 0:
            raise ContextBuilderInputError("rag_max_context_chars must not be negative.")
        if self.settings.rag_max_sources < 0:
            raise ContextBuilderInputError("rag_max_sources must not be negative.")

    def build(self, query: str, results: Iterable[SearchResult]) -> RAGContext:
        normalized_query = self._validate_query(query)
        validated = self._validate_results(results)
        ordered = self._order_results(self._deduplicate(validated))

        sources: list[RetrievedSource] = []
        for result in ordered:
            if len(sources) >= self.settings.rag_max_sources:
                break
            source = RetrievedSource.model_validate(result.model_dump())
            candidate_sources = [*sources, source]
            candidate_text = self._format_context(candidate_sources)
            if len(candidate_text) > self.settings.rag_max_context_chars:
                break
            sources.append(source)

        context_text = self._format_context(sources)
        return RAGContext(
            query=normalized_query,
            sources=sources,
            context_text=context_text,
            source_count=len(sources),
            total_characters=sum(len(source.text) for source in sources),
            total_words=sum(source.word_count or len(source.text.split()) for source in sources),
        )

    @staticmethod
    def _validate_query(query: Any) -> str:
        if not isinstance(query, str) or not query.strip():
            raise ContextBuilderInputError("Query must contain non-whitespace characters.")
        return query.strip()

    @staticmethod
    def _validate_results(results: Iterable[SearchResult]) -> list[SearchResult]:
        if isinstance(results, (str, bytes)):
            raise ContextBuilderInputError("Retrieval results must be an iterable of SearchResult objects.")
        try:
            candidates = list(results)
        except TypeError as error:
            raise ContextBuilderInputError("Retrieval results must be iterable.") from error

        for result in candidates:
            if not isinstance(result, SearchResult):
                raise ContextBuilderInputError("Each retrieval result must be a SearchResult.")
            chunk_id = getattr(result, "chunk_id", None)
            video_id = getattr(result, "video_id", None)
            text = getattr(result, "text", None)
            score = getattr(result, "score", None)
            start_time = getattr(result, "start_time", None)
            end_time = getattr(result, "end_time", None)
            if chunk_id is None:
                raise ContextBuilderInputError("Retrieved chunk_id is required.")
            if not isinstance(video_id, str) or not video_id.strip():
                raise ContextBuilderInputError("Retrieved video_id is required.")
            if not isinstance(text, str) or not text.strip():
                raise ContextBuilderInputError("Retrieved text must contain non-whitespace characters.")
            if not ContextBuilder._is_finite(score):
                raise ContextBuilderInputError("Retrieved score must be finite.")
            if not ContextBuilder._is_finite(start_time) or not ContextBuilder._is_finite(end_time):
                raise ContextBuilderInputError("Retrieved timestamps must be finite.")
            if start_time < 0 or end_time < start_time:
                raise ContextBuilderInputError("Retrieved timestamps are invalid.")
        return candidates

    @staticmethod
    def _is_finite(value: Any) -> bool:
        try:
            return math.isfinite(value)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _deduplicate(results: list[SearchResult]) -> list[SearchResult]:
        best_by_key: dict[tuple[str, int], SearchResult] = {}
        for result in results:
            key = (result.video_id, result.chunk_id)
            current = best_by_key.get(key)
            if current is None or result.score > current.score:
                best_by_key[key] = result

        ranked = sorted(best_by_key.values(), key=lambda result: result.score, reverse=True)
        unique: list[SearchResult] = []
        for result in ranked:
            if any(
                previous.video_id == result.video_id
                and previous.text.strip() == result.text.strip()
                and ContextBuilder._is_adjacent_or_overlapping(previous, result)
                for previous in unique
            ):
                continue
            unique.append(result)
        return unique

    @staticmethod
    def _is_adjacent_or_overlapping(left: SearchResult, right: SearchResult) -> bool:
        time_overlap = left.start_time <= right.end_time and right.start_time <= left.end_time
        index_adjacent = abs(left.chunk_index - right.chunk_index) <= 1
        return time_overlap or index_adjacent

    @staticmethod
    def _order_results(results: list[SearchResult]) -> list[SearchResult]:
        groups: OrderedDict[str, list[SearchResult]] = OrderedDict()
        for result in results:
            groups.setdefault(result.video_id, []).append(result)

        grouped = sorted(
            groups.values(),
            key=lambda group: (-max(result.score for result in group), results.index(group[0])),
        )
        ordered: list[SearchResult] = []
        for group in grouped:
            ordered.extend(sorted(group, key=lambda result: (result.start_time, result.chunk_index, -result.score)))
        return ordered

    @classmethod
    def _format_context(cls, sources: list[RetrievedSource]) -> str:
        blocks = []
        for index, source in enumerate(sources, start=1):
            blocks.append(
                "\n".join(
                    [
                        f"[Source {index}]",
                        f"Video ID: {source.video_id}",
                        f"Chunk ID: {source.chunk_id}",
                        f"Timestamp: {cls._format_timestamp(source.start_time)} - {cls._format_timestamp(source.end_time)}",
                        f"Relevance: {source.score:.6f}",
                        "",
                        "Transcript:",
                        source.text,
                    ]
                )
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total_seconds = int(seconds)
        minutes, remainder = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{remainder:02d}" if hours else f"{minutes:02d}:{remainder:02d}"