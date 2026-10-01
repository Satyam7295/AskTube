from __future__ import annotations

import re
import time
from collections.abc import Iterable
from typing import Any

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig

from app.core.config import Settings, get_settings
from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.transcript import TranscriptResponse, TranscriptSegment


class TranscriptServiceError(Exception):
    """Base error for failures while retrieving a video transcript."""


class TranscriptNotAvailableError(TranscriptServiceError):
    pass


class VideoUnavailableError(TranscriptServiceError):
    pass


class TranscriptProviderError(TranscriptServiceError):
    def __init__(
        self,
        message: str,
        *,
        video_id: str = "",
        language: str | None = None,
        operation: str = "fetch",
        error_code: str = "TRANSIENT_PROVIDER_ERROR",
        status_code: int | None = None,
    ) -> None:
        self.video_id = video_id
        self.language = language
        self.operation = operation
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)


class TranscriptRateLimitError(TranscriptProviderError):
    pass


class TranscriptProvider:
    def get_transcript(self, video_id: str, language: str | None = None) -> tuple[Any, Any]:
        raise NotImplementedError


class _TimeoutSession(requests.Session):
    def __init__(self, timeout: float) -> None:
        super().__init__()
        self._timeout = timeout

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self._timeout)
        return super().request(method, url, **kwargs)


class YouTubeTranscriptProvider(TranscriptProvider):
    def __init__(
        self,
        settings: Settings | None = None,
        transcript_api: YouTubeTranscriptApi | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if transcript_api is not None:
            self.api = transcript_api
        else:
            proxy_config = None
            if self.settings.transcript_proxy_http or self.settings.transcript_proxy_https:
                proxy_config = GenericProxyConfig(
                    http_url=self.settings.transcript_proxy_http,
                    https_url=self.settings.transcript_proxy_https,
                )
            self.api = YouTubeTranscriptApi(
                proxy_config=proxy_config,
                http_client=_TimeoutSession(self.settings.transcript_provider_timeout),
            )

    def get_transcript(self, video_id: str, language: str | None = None) -> tuple[Any, Any]:
        transcript_list = self.api.list(video_id)
        transcript = TranscriptService._select_transcript(transcript_list, language)
        fetched = transcript.fetch()
        snippets = fetched.snippets if hasattr(fetched, "snippets") else fetched
        return transcript, snippets


class TranscriptService:
    video_id_pattern = re.compile(r"^[A-Za-z0-9_-]{11}$")

    def __init__(
        self,
        transcript_api: YouTubeTranscriptApi | None = None,
        transcript_repository: TranscriptRepository | None = None,
        provider: TranscriptProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or YouTubeTranscriptProvider(self.settings, transcript_api)
        self.transcript_repository = transcript_repository or TranscriptRepository()

    def get_transcript(self, video_id: str, language: str | None = None) -> TranscriptResponse:
        self._validate_video_id(video_id)
        stored = self.transcript_repository.get(video_id, language)
        if stored is not None:
            return self._response_from_stored(stored)

        transcript, snippets = self._fetch_provider_transcript(video_id, language)

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

    def _fetch_provider_transcript(self, video_id: str, language: str | None) -> tuple[Any, Any]:
        max_attempts = max(1, self.settings.transcript_max_retries)
        for attempt in range(max_attempts):
            try:
                return self.provider.get_transcript(video_id, language)
            except Exception as error:
                classified = self._classify_provider_error(error, video_id, language, "fetch")
                if not self._is_retryable(error) or attempt == max_attempts - 1:
                    raise classified from error
                time.sleep(self.settings.transcript_retry_backoff_seconds * (2**attempt))
        raise AssertionError("provider retry loop did not return or raise")

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
    def _classify_provider_error(
        error: Exception, video_id: str, language: str | None, operation: str
    ) -> TranscriptServiceError:
        error_name = type(error).__name__
        if error_name in {"NoTranscriptFound", "TranscriptsDisabled"}:
            return TranscriptNotAvailableError("Transcript is not available for this video.")
        if error_name in {"VideoUnavailable", "InvalidVideoId"}:
            return VideoUnavailableError("Video was not found or is unavailable.")
        if isinstance(error, TranscriptServiceError):
            return error

        status_code = getattr(error, "status_code", None)
        if status_code is None:
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
        if error_name in {"IpBlocked", "RequestBlocked"} or "blocked" in error_name.lower():
            code = "PROVIDER_AUTH_ERROR"
        elif status_code == 429 or error_name in {"TooManyRequests", "RateLimitError"}:
            code = "PROVIDER_RATE_LIMIT"
        elif isinstance(status_code, int) and 400 <= status_code < 500:
            code = "PERMANENT_PROVIDER_ERROR"
        elif isinstance(error, (TimeoutError, ConnectionError)) or error_name in {
            "ConnectError", "ReadTimeout", "ConnectTimeout", "TimeoutException"
        }:
            code = "NETWORK_ERROR"
        else:
            code = "TRANSIENT_PROVIDER_ERROR"
        if code == "PROVIDER_AUTH_ERROR":
            message = f"{code}: YouTube blocked transcript access for this deployment."
        elif code == "PROVIDER_RATE_LIMIT":
            message = f"{code}: YouTube rate-limited transcript access."
        else:
            detail = str(error).strip() or error_name
            message = (
                f"{code}: transcript provider {operation} failed for video_id={video_id} "
                f"language={language or 'auto'}: {detail}"
            )
        error_type = TranscriptRateLimitError if code == "PROVIDER_RATE_LIMIT" else TranscriptProviderError
        return error_type(
            message,
            video_id=video_id,
            language=language,
            operation=operation,
            error_code=code,
            status_code=status_code if isinstance(status_code, int) else None,
        )

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        error_name = type(error).__name__
        status_code = getattr(error, "status_code", None)
        response = getattr(error, "response", None)
        status_code = status_code or getattr(response, "status_code", None)
        return (
            status_code == 429
            or error_name in {"TooManyRequests", "RateLimitError", "ConnectError", "ReadTimeout", "ConnectTimeout"}
            or isinstance(error, (TimeoutError, ConnectionError))
        )