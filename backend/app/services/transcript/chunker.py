from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ChunkingConfig:
    target_words: int = 600
    overlap_words: int = 80

    def __post_init__(self) -> None:
        if self.target_words <= 0:
            raise ValueError("target_words must be positive.")
        if self.overlap_words < 0:
            raise ValueError("overlap_words cannot be negative.")
        if self.overlap_words >= self.target_words:
            raise ValueError("overlap_words must be smaller than target_words.")


class TranscriptChunker:
    def __init__(self, config: ChunkingConfig | None = None) -> None:
        self.config = config or ChunkingConfig()

    def chunk(self, video_id: str, language_code: str, segments: Sequence[Any]) -> list[dict[str, Any]]:
        normalized = [self._normalize_segment(segment) for segment in segments]
        chunks: list[dict[str, Any]] = []
        start_index = 0

        while start_index < len(normalized):
            end_index = start_index
            word_count = 0
            while end_index < len(normalized):
                segment_words = normalized[end_index]["word_count"]
                if end_index > start_index and word_count + segment_words > self.config.target_words:
                    break
                word_count += segment_words
                end_index += 1

            included = normalized[start_index:end_index]
            chunks.append(self._build_chunk(video_id, language_code, len(chunks), start_index, end_index, included))
            if end_index == len(normalized):
                break

            next_start = end_index
            overlap_count = 0
            cursor = end_index - 1
            while cursor >= start_index and overlap_count < self.config.overlap_words:
                overlap_count += normalized[cursor]["word_count"]
                cursor -= 1
            candidate = cursor + 1
            if candidate > start_index:
                next_start = candidate
            start_index = next_start

        return chunks

    @staticmethod
    def _normalize_segment(segment: Any) -> dict[str, Any]:
        if isinstance(segment, dict):
            text = segment.get("text", "")
            start = segment.get("start", 0.0)
            duration = segment.get("duration", 0.0)
        else:
            text = getattr(segment, "text", "")
            start = getattr(segment, "start", 0.0)
            duration = getattr(segment, "duration", 0.0)
        normalized_text = " ".join(str(text).split())
        return {
            "text": normalized_text,
            "start": float(start),
            "duration": float(duration),
            "word_count": len(normalized_text.split()),
        }

    @staticmethod
    def _build_chunk(
        video_id: str,
        language_code: str,
        chunk_index: int,
        start_index: int,
        end_index: int,
        segments: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        text = " ".join(segment["text"] for segment in segments).strip()
        first = segments[0]
        last = segments[-1]
        return {
            "video_id": video_id,
            "language_code": language_code,
            "chunk_index": chunk_index,
            "text": text,
            "start_time": first["start"],
            "end_time": last["start"] + last["duration"],
            "segment_start_index": start_index,
            "segment_end_index": end_index - 1,
            "character_count": len(text),
            "word_count": sum(segment["word_count"] for segment in segments),
        }