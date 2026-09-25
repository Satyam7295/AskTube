from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from youtube_transcript_api import YouTubeTranscriptApi

from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.transcript import TranscriptResponse, TranscriptSegment


class TranscriptServiceError(Exception):
    """Base error for failures while retrieving a video transcript."""


class TranscriptNotAvailableError(TranscriptServiceError):
    pass


class VideoUnavailableError(TranscriptServiceError):
    pass


class TranscriptProviderError(TranscriptServiceError):
    pass


class TranscriptService:
    video_id_pattern = re.compile(r"^[A-Za-z0-9_-]{11}$")

    def __init__(
        self,
        transcript_api: YouTubeTranscriptApi | None = None,
        transcript_repository: TranscriptRepository | None = None,
    ) -> None:
        self.transcript_api = transcript_api or YouTubeTranscriptApi()
        self.transcript_repository = transcript_repository or TranscriptRepository()

    def get_transcript(self, video_id: str, language: str | None = None) -> TranscriptResponse:
        self._validate_video_id(video_id)
        stored = self.transcript_repository.get(video_id, language)
        if stored is not None:
            return self._response_from_stored(stored)

        try:
            transcript_list = self.transcript_api.list(video_id)
            transcript = self._select_transcript(transcript_list, language)
            fetched = transcript.fetch()
            snippets = fetched.snippets if hasattr(fetched, "snippets") else fetched
        except Exception as error:
            self._raise_provider_error(error)

        segments = [self._segment(snippet) for snippet in snippets]
        response = TranscriptResponse(
            video_id=video_id,
            language=getattr(transcript, "language_code", None),
            is_generated=getattr(transcript, "is_generated", None),
            segments=segments,
            total_segments=len(segments),
        )
        self.transcript_repository.upsert(
            {
                "video_id": response.video_id,
                "language_code": response.language or language or "en",
                "language_name": getattr(transcript, "language", None),
                "is_generated": response.is_generated,
                "segments": [segment.model_dump() for segment in response.segments],
            }
        )
        return response

    @staticmethod
    def _response_from_stored(stored: Any) -> TranscriptResponse:
        segments = [TranscriptSegment.model_validate(segment) for segment in stored.segments]
        return TranscriptResponse(
            video_id=stored.video_id,
            language=stored.language_code,
            is_generated=stored.is_generated,
            segments=segments,
            total_segments=len(segments),
        )

    @classmethod
    def _validate_video_id(cls, video_id: str) -> None:
        if not cls.video_id_pattern.fullmatch(video_id):
            raise ValueError("Invalid YouTube video ID.")

    @staticmethod
    def _select_transcript(transcript_list: Iterable[Any], language: str | None) -> Any:
        transcripts = list(transcript_list)
        if not transcripts:
            raise TranscriptNotAvailableError("Transcript is not available for this video.")

        preferred_language = language or "en"
        return next(
            (transcript for transcript in transcripts if getattr(transcript, "language_code", None) == preferred_language),
            transcripts[0],
        )

    @staticmethod
    def _segment(snippet: Any) -> TranscriptSegment:
        if isinstance(snippet, dict):
            text = snippet["text"]
            start = snippet["start"]
            duration = snippet["duration"]
        else:
            text = snippet.text
            start = snippet.start
            duration = snippet.duration
        return TranscriptSegment(
            text=re.sub(r"\s+", " ", str(text)).strip(),
            start=float(start),
            duration=float(duration),
        )

    @staticmethod
    def _raise_provider_error(error: Exception) -> None:
        error_name = type(error).__name__
        if error_name in {"NoTranscriptFound", "TranscriptsDisabled"}:
            raise TranscriptNotAvailableError("Transcript is not available for this video.") from error
        if error_name in {"VideoUnavailable", "InvalidVideoId"}:
            raise VideoUnavailableError("Video was not found or is unavailable.") from error
        if isinstance(error, TranscriptServiceError):
            raise error
        raise TranscriptProviderError("Transcript provider request failed.") from error