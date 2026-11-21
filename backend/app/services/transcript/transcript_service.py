from __future__ import annotations

import re
import time
import logging
import random
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import requests
from youtube_transcript_api import (
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    YouTubeTranscriptApi,
)
from youtube_transcript_api.proxies import GenericProxyConfig

from app.core.config import Settings, get_settings
from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.transcript import TranscriptResponse, TranscriptSegment


class TranscriptServiceError(Exception):
    """Base error for failures while retrieving a video transcript."""


class TranscriptNotAvailableError(TranscriptServiceError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "TRANSCRIPT_NOT_FOUND",
        video_id: str = "",
    ) -> None:
        self.error_code = error_code
        self.video_id = video_id
        super().__init__(message)


class VideoUnavailableError(TranscriptServiceError):
    def __init__(self, message: str, *, video_id: str = "") -> None:
        self.error_code = "VIDEO_UNAVAILABLE"
        self.video_id = video_id
        super().__init__(message)


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
        provider_name: str = "youtube",
    ) -> None:
        self.video_id = video_id
        self.language = language
        self.operation = operation
        self.error_code = error_code
        self.status_code = status_code
        self.provider_name = provider_name
        super().__init__(message)


class TranscriptRateLimitError(TranscriptProviderError):
    pass


class TranscriptProvider:
    name = "unknown"

    def get_transcript(self, video_id: str, language: str | None = None) -> tuple[Any, Any]:
        raise NotImplementedError


class AuthorizedHttpTranscriptProvider(TranscriptProvider):
    """Connector for an operator-approved transcript service endpoint."""

    name = "authorized_fallback"

    def __init__(self, url: str, api_key: str | None, timeout: float) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("TRANSCRIPT_FALLBACK_URL must be an HTTP(S) URL.")
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

    def get_transcript(self, video_id: str, language: str | None = None) -> tuple[Any, Any]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        response = requests.post(
            self.url,
            json={"video_id": video_id, "language": language or "en"},
            headers=headers,
            timeout=self.timeout,
        )
        if response.status_code == 404:
            raise TranscriptFallbackUnavailable("Transcript is not available.")
        if response.status_code == 401 or response.status_code == 403:
            raise ConnectionAborted("The fallback provider authentication is invalid.")
        if response.status_code == 429:
            raise TranscriptFallbackRateLimit("The fallback provider rate-limited the request.")
        response.raise_for_status()
        payload = response.json()
        transcript_payload = payload.get("transcript") if isinstance(payload, dict) else None
        if isinstance(transcript_payload, dict):
            payload = transcript_payload
        segments = payload.get("segments") if isinstance(payload, dict) else None
        if not isinstance(segments, list):
            raise TranscriptProviderError(
                "PROVIDER_INVALID_RESPONSE: fallback provider returned no transcript segments.",
                video_id=video_id,
                language=language,
                error_code="PROVIDER_INVALID_RESPONSE",
                provider_name=self.name,
            )
        transcript = SimpleNamespace(
            language_code=payload.get("language_code") or payload.get("language") or language or "en",
            is_generated=payload.get("is_generated"),
            language=payload.get("language_name"),
        )
        snippet_objects = [
            SimpleNamespace(
                text=str(segment["text"]),
                start=float(segment["start"]),
                duration=float(segment["duration"]),
            )
            for segment in segments
        ]
        return transcript, snippet_objects


class TranscriptFallbackRateLimit(Exception):
    pass


class TranscriptFallbackUnavailable(Exception):
    pass


class _TimeoutSession(requests.Session):
    def __init__(self, timeout: float) -> None:
        super().__init__()
        self._timeout = timeout

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self._timeout)
        return super().request(method, url, **kwargs)


class YouTubeTranscriptProvider(TranscriptProvider):
    name = "youtube"

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
            proxy_enabled = (
                self.settings.youtube_proxy_enabled
                or self.settings.transcript_proxy_enabled
            )
            if proxy_enabled and (self.settings.transcript_proxy_http or self.settings.transcript_proxy_https):
                http_url = self._proxy_url(self.settings.transcript_proxy_http)
                https_url = self._proxy_url(self.settings.transcript_proxy_https)
                proxy_config = GenericProxyConfig(
                    http_url=http_url,
                    https_url=https_url,
                )
            self.api = YouTubeTranscriptApi(
                proxy_config=proxy_config,
                http_client=_TimeoutSession(self.settings.transcript_provider_timeout),
            )

    def _proxy_url(self, url: str | None) -> str | None:
        if not url:
            return None
        username = self.settings.youtube_proxy_username or self.settings.transcript_proxy_username
        password = self.settings.youtube_proxy_password or self.settings.transcript_proxy_password
        if not username:
            return url
        scheme_separator = url.find("://")
        if scheme_separator == -1:
            return url
        auth = quote(username, safe="")
        if password:
            auth += ":" + quote(password, safe="")
        return f"{url[: scheme_separator + 3]}{auth}@{url[scheme_separator + 3:]}"

    def get_transcript(self, video_id: str, language: str | None = None) -> tuple[Any, Any]:
        preferred_languages = [language, "en"] if language and language != "en" else ["en"]
        fetched = self.api.fetch(video_id, languages=preferred_languages)
        if hasattr(fetched, "snippets"):
            snippets = fetched.snippets
        elif hasattr(fetched, "fetch"):
            fetched_result = fetched.fetch()
            snippets = fetched_result.snippets if hasattr(fetched_result, "snippets") else fetched_result
        else:
            snippets = fetched
        return fetched, snippets


logger = logging.getLogger(__name__)


@dataclass
class ProviderCircuitBreaker:
    failure_threshold: int = 3
    cooldown_seconds: float = 300.0

    def __post_init__(self) -> None:
        self._lock = Lock()
        self._state = "closed"
        self._failure_count = 0
        self._opened_at: float | None = None

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "open" and self._opened_at is not None:
                if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                    self._state = "half-open"
            return self._state

    def allow_request(self) -> bool:
        return self.state != "open"

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = "closed"
            self._opened_at = None

    def record_failure(self, error: TranscriptServiceError) -> None:
        code = getattr(error, "error_code", "")
        if code not in {
            "PROVIDER_IP_BLOCKED",
            "PROVIDER_REQUEST_BLOCKED",
            "PROVIDER_RATE_LIMIT",
            "NETWORK_ERROR",
            "TRANSIENT_PROVIDER_ERROR",
            "PROVIDER_UNKNOWN_ERROR",
        }:
            return
        with self._lock:
            if code in {"PROVIDER_IP_BLOCKED", "PROVIDER_REQUEST_BLOCKED"}:
                self._failure_count = max(self.failure_threshold, self._failure_count + 1)
            else:
                self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()


class ProviderMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._values: dict[str, dict[str, int]] = {}

    def record(self, provider_name: str, outcome: str) -> None:
        with self._lock:
            provider = self._values.setdefault(provider_name, {})
            provider[outcome] = provider.get(outcome, 0) + 1

    def snapshot(self) -> dict[str, dict[str, int]]:
        with self._lock:
            return {name: dict(values) for name, values in self._values.items()}


def parsed_query_video_id(query: str) -> str | None:
    return parse_qs(query).get("v", [None])[0]


def extract_youtube_video_id(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid YouTube URL or video ID.")
    value = value.strip()
    if re.fullmatch(r"^[A-Za-z0-9_-]{11}$", value):
        return value
    if not value:
        raise ValueError("Invalid YouTube URL or video ID.")

    candidate = value
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        parsed = urlparse(candidate)
    except ValueError as error:
        raise ValueError("Invalid YouTube URL or video ID.") from error

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Invalid YouTube URL or video ID.")
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www.") or hostname.startswith("m.") or hostname.startswith("music."):
        hostname = hostname.split(".", 1)[1]

    video_id: str | None = None
    if hostname == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif hostname == "youtube.com":
        if parsed.path.startswith("/watch"):
            video_id = parsed_query_video_id(parsed.query)
        elif parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/") or parsed.path.startswith("/live/") or parsed.path.startswith("/v/"):
            video_id = parsed.path.strip("/").split("/", 2)[1]

    if video_id and re.fullmatch(r"^[A-Za-z0-9_-]{11}$", video_id):
        return video_id
    if "://" not in value and "/" not in value and "." not in value:
        raise ValueError("Invalid YouTube video ID.")
    raise ValueError("Invalid YouTube URL or video ID.")


class TranscriptService:
    video_id_pattern = re.compile(r"^[A-Za-z0-9_-]{11}$")

    def __init__(
        self,
        transcript_api: YouTubeTranscriptApi | None = None,
        transcript_repository: TranscriptRepository | None = None,
        provider: TranscriptProvider | None = None,
        fallback_provider: TranscriptProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or YouTubeTranscriptProvider(self.settings, transcript_api)
        if fallback_provider is not None:
            self.fallback_provider = fallback_provider
        elif self.settings.transcript_fallback_url:
            self.fallback_provider = AuthorizedHttpTranscriptProvider(
                self.settings.transcript_fallback_url,
                self.settings.transcript_fallback_api_key,
                self.settings.transcript_provider_timeout,
            )
        else:
            self.fallback_provider = None
        self.transcript_repository = transcript_repository or TranscriptRepository()
        self.provider_metrics = ProviderMetrics()
        threshold = max(1, self.settings.transcript_circuit_failure_threshold)
        cooldown = max(0.01, self.settings.transcript_circuit_cooldown_seconds)
        self.provider_circuits = {
            getattr(self.provider, "name", "youtube"): ProviderCircuitBreaker(threshold, cooldown),
        }
        if self.fallback_provider is not None:
            self.provider_circuits[getattr(self.fallback_provider, "name", "fallback")] = ProviderCircuitBreaker(
                threshold,
                cooldown,
            )

    def get_transcript(self, video_id: str, language: str | None = None) -> TranscriptResponse:
        video_id = self.extract_video_id(video_id)
        self._validate_video_id(video_id)
        try:
            stored = self.transcript_repository.get(
                video_id,
                language,
                max_age_hours=max(0, self.settings.transcript_cache_ttl_hours),
            )
        except TypeError:
            stored = self.transcript_repository.get(video_id, language)
        if stored is not None:
            return self._response_from_stored(stored)

        logger.info(
            "Transcript retrieval started",
            extra={"video_id": video_id, "language": language or "auto", "indexing_stage": "transcript"},
        )
        transcript, snippets = self._fetch_provider_transcript(video_id, language)

        segments = [self._segment(snippet) for snippet in snippets]
        response = TranscriptResponse(
            video_id=video_id,
            language=getattr(transcript, "language_code", None),
            is_generated=getattr(transcript, "is_generated", None),
            segments=segments,
            total_segments=len(segments),
        )
        logger.info(
            "Transcript successfully retrieved",
            extra={
                "video_id": video_id,
                "language": language or "auto",
                "provider_name": getattr(self, "_selected_provider_name", getattr(self.provider, "name", "unknown")),
                "indexing_stage": "transcript",
            },
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

    def get_provider_metrics(self) -> dict[str, dict[str, int]]:
        return self.provider_metrics.snapshot()

    def get_circuit_states(self) -> dict[str, str]:
        return {name: circuit.state for name, circuit in self.provider_circuits.items()}

    def _fetch_provider_transcript(self, video_id: str, language: str | None) -> tuple[Any, Any]:
        max_attempts = max(1, self.settings.transcript_max_retries)
        providers = [self.provider]
        if self.fallback_provider is not None:
            providers.append(self.fallback_provider)
        last_error: TranscriptServiceError | None = None
        primary_blocked_error: TranscriptServiceError | None = None

        for provider_index, provider in enumerate(providers):
            provider_name = getattr(provider, "name", provider.__class__.__name__)
            circuit = self.provider_circuits.get(provider_name)
            if circuit is not None and not circuit.allow_request():
                logger.warning(
                    "Transcript provider circuit is open",
                    extra={
                        "video_id": video_id,
                        "provider_name": provider_name,
                        "error_code": "CIRCUIT_OPEN",
                        "indexing_stage": "transcript",
                    },
                )
                continue

            logger.info(
                "Transcript provider selected",
                extra={"video_id": video_id, "provider_name": provider_name, "indexing_stage": "transcript"},
            )
            for attempt in range(max_attempts):
                try:
                    result = provider.get_transcript(video_id, language)
                    if circuit is not None:
                        circuit.record_success()
                    self.provider_metrics.record(provider_name, "success")
                    self._selected_provider_name = provider_name
                    logger.info(
                        "Transcript successfully retrieved",
                        extra={
                            "video_id": video_id,
                            "provider_name": provider_name,
                            "indexing_stage": "transcript",
                            "fallback_used": "true" if provider_index > 0 else "false",
                        },
                    )
                    return result
                except Exception as error:
                    classified = self._classify_provider_error(error, video_id, language, "fetch")
                    if hasattr(classified, "provider_name"):
                        classified.provider_name = provider_name
                    last_error = classified
                    error_code = getattr(classified, "error_code", "")
                    if provider_index == 0 and error_code in {
                        "PROVIDER_IP_BLOCKED",
                        "PROVIDER_REQUEST_BLOCKED",
                    }:
                        primary_blocked_error = classified
                    if circuit is not None:
                        circuit.record_failure(classified)
                    self.provider_metrics.record(provider_name, "failure")

                    logger.warning(
                        "Transcript retrieval failed",
                        extra={
                            "video_id": video_id,
                            "provider_name": provider_name,
                            "error_code": error_code,
                            "indexing_stage": "transcript",
                            "circuit_state": circuit.state if circuit is not None else "not_configured",
                        },
                    )

                    if isinstance(classified, (TranscriptNotAvailableError, VideoUnavailableError)):
                        if provider_index == 0 and self.fallback_provider is not None:
                            break
                        raise classified from error
                    if error_code in {"PROVIDER_IP_BLOCKED", "PROVIDER_REQUEST_BLOCKED"}:
                        break
                    if not self._is_retryable(classified) or attempt == max_attempts - 1:
                        break

                    delay = min(30.0, self.settings.transcript_retry_backoff_seconds * (2**attempt))
                    delay += random.uniform(0, delay * 0.25)
                    time.sleep(delay)

        if last_error is not None:
            if primary_blocked_error is not None:
                last_error = primary_blocked_error
            raise last_error
        raise TranscriptProviderError(
            "PROVIDER_UNKNOWN_ERROR: no transcript provider was able to retrieve the transcript.",
            video_id=video_id,
            language=language,
            error_code="PROVIDER_UNKNOWN_ERROR",
            provider_name="none",
        )

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
    def extract_video_id(cls, value: str) -> str:
        return extract_youtube_video_id(value)

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
        if isinstance(error, TranscriptFallbackUnavailable) or error_name == "TranscriptFallbackUnavailable":
            return TranscriptNotAvailableError(
                "Transcript is not available for this video.",
                error_code="TRANSCRIPT_NOT_FOUND",
                video_id=video_id,
            )
        if isinstance(error, TranscriptFallbackRateLimit) or error_name == "TranscriptFallbackRateLimit":
            return TranscriptRateLimitError(
                "PROVIDER_RATE_LIMIT: The fallback provider rate-limited transcript access.",
                video_id=video_id,
                language=language,
                operation=operation,
                error_code="PROVIDER_RATE_LIMIT",
                provider_name="authorized_fallback",
            )
        if isinstance(error, NoTranscriptFound) or error_name == "NoTranscriptFound":
            return TranscriptNotAvailableError(
                "Transcript is not available for this video.",
                error_code="TRANSCRIPT_NOT_FOUND",
                video_id=video_id,
            )
        if isinstance(error, TranscriptsDisabled) or error_name == "TranscriptsDisabled":
            return TranscriptNotAvailableError(
                "Captions are disabled for this video.",
                error_code="TRANSCRIPTS_DISABLED",
                video_id=video_id,
            )
        if isinstance(error, VideoUnavailable) or error_name in {"VideoUnavailable", "InvalidVideoId"}:
            return VideoUnavailableError("Video was not found or is unavailable.", video_id=video_id)
        if isinstance(error, TranscriptServiceError):
            return error

        status_code = getattr(error, "status_code", None)
        if status_code is None:
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
        if isinstance(error, IpBlocked) or error_name == "IpBlocked":
            code = "PROVIDER_IP_BLOCKED"
        elif isinstance(error, RequestBlocked) or error_name == "RequestBlocked":
            code = "PROVIDER_REQUEST_BLOCKED"
        elif error_name in {"ConnectionAborted", "CookieError", "CookieInvalid", "PoTokenRequired", "FailedToCreateConsentCookie"}:
            code = "PROVIDER_AUTH_ERROR"
        elif status_code == 429 or error_name in {"TooManyRequests", "RateLimitError"}:
            code = "PROVIDER_RATE_LIMIT"
        elif isinstance(status_code, int) and 400 <= status_code < 500:
            code = "PERMANENT_PROVIDER_ERROR"
        elif isinstance(error, (TimeoutError, ConnectionError)) or error_name in {
            "ConnectError", "ReadTimeout", "ConnectTimeout", "TimeoutException", "Timeout",
            "ConnectTimeoutError", "ReadTimeoutError",
        }:
            code = "NETWORK_ERROR"
        else:
            code = "PROVIDER_UNKNOWN_ERROR"
        if code in {"PROVIDER_IP_BLOCKED", "PROVIDER_REQUEST_BLOCKED"}:
            message = f"{code}: YouTube blocked transcript access for this deployment."
        elif code == "PROVIDER_AUTH_ERROR":
            message = f"{code}: The transcript provider authentication is invalid or unavailable."
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
        if isinstance(error, TranscriptProviderError):
            return error.error_code in {
                "PROVIDER_RATE_LIMIT",
                "NETWORK_ERROR",
                "TRANSIENT_PROVIDER_ERROR",
                "PROVIDER_UNKNOWN_ERROR",
            }
        status_code = getattr(error, "status_code", None)
        response = getattr(error, "response", None)
        status_code = status_code or getattr(response, "status_code", None)
        return (
            status_code == 429
            or error_name in {
                "TooManyRequests",
                "RateLimitError",
                "ConnectError",
                "ReadTimeout",
                "ConnectTimeout",
                "Timeout",
                "ConnectTimeoutError",
                "ReadTimeoutError",
            }
            or isinstance(error, (TimeoutError, ConnectionError))
        )