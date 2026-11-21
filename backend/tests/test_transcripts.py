from types import SimpleNamespace
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.db.database as database_module
from app.main import app
from app.db.base import Base
from app.models.transcript import Transcript
from app.repositories.transcript_repository import TranscriptDatabaseError, TranscriptRepository
from app.services.transcript.transcript_service import TranscriptService
from app.core.config import Settings
from app.services.transcript.transcript_service import (
    AuthorizedHttpTranscriptProvider,
    TranscriptProvider,
    YouTubeTranscriptProvider,
)


VIDEO_ID = "dQw4w9WgXcQ"


@pytest.fixture(autouse=True)
def transcript_database() -> None:
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    database_module.engine = engine
    database_module.SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    yield
    engine.dispose()


class FakeTranscript:
    def __init__(self, language_code: str, is_generated: bool, snippets: list[dict]) -> None:
        self.language_code = language_code
        self.is_generated = is_generated
        self._snippets = snippets

    def fetch(self) -> SimpleNamespace:
        return SimpleNamespace(snippets=[SimpleNamespace(**snippet) for snippet in self._snippets])


def client() -> TestClient:
    return TestClient(app)


def test_successful_transcript_preserves_response_fields() -> None:
    transcript = FakeTranscript("en", False, [
        {"text": " Welcome   to the lecture. ", "start": 0.0, "duration": 3.2},
        {"text": "Today we will discuss binary search.", "start": 3.2, "duration": 5.4},
    ])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.return_value = transcript
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 200
    assert response.json() == {
        "video_id": VIDEO_ID,
        "language": "en",
        "is_generated": False,
        "segments": [
            {"text": "Welcome to the lecture.", "start": 0.0, "duration": 3.2},
            {"text": "Today we will discuss binary search.", "start": 3.2, "duration": 5.4},
        ],
        "total_segments": 2,
    }


def test_fractional_timestamps_are_not_rounded() -> None:
    transcript = FakeTranscript("en", True, [{"text": "A point in time", "start": 12.43, "duration": 15.38}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.return_value = transcript
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.json()["segments"] == [{"text": "A point in time", "start": 12.43, "duration": 15.38}]


def test_no_transcript_returns_not_found() -> None:
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.side_effect = type("NoTranscriptFound", (Exception,), {})("missing")
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 404
    assert response.json()["detail"] == "Transcript is not available for this video."


def test_video_unavailable_returns_not_found() -> None:
    unavailable = type("VideoUnavailable", (Exception,), {})
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.side_effect = unavailable()
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 404
    assert response.json()["detail"] == "Video was not found or is unavailable."


def test_provider_failure_returns_bad_gateway() -> None:
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.side_effect = RuntimeError("provider down")
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 502
    assert response.json()["detail"].startswith("PROVIDER_UNKNOWN_ERROR:")
    assert "video_id=dQw4w9WgXcQ" in response.json()["detail"]
    assert "provider down" in response.json()["detail"]


def test_ip_block_is_classified_without_retrying() -> None:
    blocked = type("IpBlocked", (Exception,), {})
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.side_effect = blocked("YouTube blocked this IP")
        with pytest.raises(Exception) as raised:
            TranscriptService(transcript_api=api.return_value).get_transcript(VIDEO_ID)

    assert raised.value.__class__.__name__ == "TranscriptProviderError"
    assert raised.value.error_code == "PROVIDER_IP_BLOCKED"
    assert str(raised.value) == "PROVIDER_IP_BLOCKED: YouTube blocked transcript access for this deployment."
    assert api.return_value.fetch.call_count == 1


def test_request_block_is_classified_without_retrying() -> None:
    blocked = type("RequestBlocked", (Exception,), {})
    api = MagicMock()
    api.fetch.side_effect = blocked("YouTube rejected the request")

    with pytest.raises(Exception) as raised:
        TranscriptService(transcript_api=api, settings=Settings(transcript_max_retries=3)).get_transcript(VIDEO_ID)

    assert raised.value.error_code == "PROVIDER_REQUEST_BLOCKED"
    assert api.fetch.call_count == 1


def test_disabled_and_missing_transcripts_have_distinct_codes() -> None:
    disabled = type("TranscriptsDisabled", (Exception,), {})
    missing = type("NoTranscriptFound", (Exception,), {})
    for exception, expected_code in ((disabled, "TRANSCRIPTS_DISABLED"), (missing, "TRANSCRIPT_NOT_FOUND")):
        api = MagicMock()
        api.fetch.side_effect = exception("unavailable")
        with pytest.raises(Exception) as raised:
            TranscriptService(transcript_api=api).get_transcript(VIDEO_ID)
        assert raised.value.error_code == expected_code
        assert api.fetch.call_count == 1


def test_transient_provider_failure_retries_then_succeeds() -> None:
    transcript = FakeTranscript("en", True, [{"text": "Retry worked", "start": 0.0, "duration": 1.0}])
    transient = TimeoutError("temporary timeout")
    with patch("app.services.transcript.transcript_service.time.sleep") as sleep:
        api = MagicMock()
        api.fetch.side_effect = [transient, transcript]
        response = TranscriptService(transcript_api=api).get_transcript(VIDEO_ID)

    assert response.total_segments == 1
    assert api.fetch.call_count == 2
    assert sleep.call_count == 1


def test_cached_transcript_bypasses_provider() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.upsert(
        {
            "video_id": VIDEO_ID,
            "language_code": "en",
            "language_name": "English",
            "is_generated": True,
            "segments": [{"text": "Cached", "start": 0.0, "duration": 1.0}],
        }
    )
    api = type("Api", (), {"list": lambda *_args: (_ for _ in ()).throw(AssertionError("provider called"))})()

    response = TranscriptService(transcript_api=api, transcript_repository=repository).get_transcript(VIDEO_ID)

    assert response.segments[0].text == "Cached"


def test_invalid_video_id_returns_validation_error() -> None:
    response = client().get("/api/videos/too-short/transcript")

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid YouTube video ID."


def test_language_selection_is_deterministic() -> None:
    spanish = FakeTranscript("es", False, [{"text": "Hola", "start": 0.0, "duration": 1.0}])
    english = FakeTranscript("en", True, [{"text": "Hello", "start": 0.0, "duration": 1.0}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.side_effect = lambda video_id, languages=(): (
            spanish if "es" in languages else english
        )
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")
        requested = client().get(f"/api/videos/{VIDEO_ID}/transcript?language=es")

    assert response.json()["language"] == "en"
    assert requested.json()["language"] == "es"


def test_service_rejects_invalid_video_id() -> None:
    with pytest.raises(ValueError, match="Invalid YouTube video ID"):
        TranscriptService(transcript_api=object()).get_transcript("invalid")


@pytest.mark.parametrize(
    "value",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
    ],
)
def test_extracts_video_ids_from_supported_youtube_urls(value: str) -> None:
    assert TranscriptService.extract_video_id(value) == VIDEO_ID


def test_rejects_invalid_youtube_host_and_url() -> None:
    with pytest.raises(ValueError, match="Invalid YouTube"):
        TranscriptService.extract_video_id("https://youtube.com.example/watch?v=dQw4w9WgXcQ")
    with pytest.raises(ValueError, match="Invalid YouTube"):
        TranscriptService.extract_video_id("not a youtube url")


def test_fetch_requests_preferred_language_then_english() -> None:
    transcript = FakeTranscript("es", False, [{"text": "Hola", "start": 0.0, "duration": 1.0}])
    api = MagicMock()
    api.fetch.return_value = transcript

    TranscriptService(transcript_api=api).get_transcript(VIDEO_ID, "es")

    api.fetch.assert_called_once_with(VIDEO_ID, languages=["es", "en"])


def test_proxy_configuration_uses_generic_proxy_config() -> None:
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api, patch(
        "app.services.transcript.transcript_service.GenericProxyConfig"
    ) as proxy:
        YouTubeTranscriptProvider(
            Settings(
                youtube_proxy_enabled=True,
                transcript_proxy_http="http://proxy.example:8080",
                transcript_proxy_https="https://proxy.example:8443",
            )
        )

    proxy.assert_called_once_with(
        http_url="http://proxy.example:8080",
        https_url="https://proxy.example:8443",
    )
    api.assert_called_once()
    assert api.call_args.kwargs["proxy_config"] is proxy.return_value


def test_proxy_credentials_are_loaded_from_environment_style_settings() -> None:
    settings = Settings(
        youtube_proxy_enabled=True,
        youtube_proxy_username="proxy-user",
        youtube_proxy_password="proxy-pass",
        transcript_proxy_http="http://proxy.example:8080",
        transcript_proxy_https="https://proxy.example:8443",
    )
    provider = YouTubeTranscriptProvider(settings=settings)
    assert provider.settings.youtube_proxy_enabled is True
    assert provider.settings.youtube_proxy_username == "proxy-user"


def test_proxy_is_disabled_by_default() -> None:
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api, patch(
        "app.services.transcript.transcript_service.GenericProxyConfig"
    ) as proxy:
        YouTubeTranscriptProvider(
            Settings(
                transcript_proxy_http="http://proxy.example:8080",
                transcript_proxy_https="https://proxy.example:8443",
            )
        )

    proxy.assert_not_called()
    assert api.call_args.kwargs["proxy_config"] is None


def test_http_429_is_normalized_without_retrying_when_retries_disabled() -> None:
    rate_limited = type("TooManyRequests", (Exception,), {"status_code": 429})
    api = MagicMock()
    api.fetch.side_effect = rate_limited("too many requests")

    with pytest.raises(Exception) as raised:
        TranscriptService(
            transcript_api=api,
            settings=Settings(transcript_max_retries=1),
        ).get_transcript(VIDEO_ID)

    assert raised.value.__class__.__name__ == "TranscriptRateLimitError"
    assert raised.value.error_code == "PROVIDER_RATE_LIMIT"
    assert str(raised.value) == "PROVIDER_RATE_LIMIT: YouTube rate-limited transcript access."
    assert api.fetch.call_count == 1


def test_transcript_is_persisted_with_timing_and_metadata() -> None:
    transcript = FakeTranscript("en", True, [{"text": "Stored", "start": 12.43, "duration": 15.38}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.return_value = transcript
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 200
    with database_module.get_session_factory()() as session:
        stored = session.query(Transcript).one()
        assert stored.video_id == VIDEO_ID
        assert stored.language_code == "en"
        assert stored.is_generated is True
        assert stored.segments == [{"text": "Stored", "start": 12.43, "duration": 15.38}]


def test_stored_transcript_is_returned_without_calling_provider() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.upsert(
        {
            "video_id": VIDEO_ID,
            "language_code": "es",
            "language_name": "Spanish",
            "is_generated": False,
            "segments": [{"text": "Hola", "start": 4.25, "duration": 1.75}],
        }
    )

    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript?language=es")

    assert response.status_code == 200
    assert response.json()["segments"] == [{"text": "Hola", "start": 4.25, "duration": 1.75}]
    assert response.json()["language"] == "es"
    assert response.json()["is_generated"] is False
    api.return_value.fetch.assert_not_called()


def test_repeated_request_does_not_create_duplicate_transcripts() -> None:
    transcript = FakeTranscript("en", False, [{"text": "Once", "start": 0.0, "duration": 1.0}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.fetch.return_value = transcript
        client().get(f"/api/videos/{VIDEO_ID}/transcript")
        client().get(f"/api/videos/{VIDEO_ID}/transcript")

    with database_module.get_session_factory()() as session:
        assert session.query(Transcript).count() == 1
    api.return_value.fetch.assert_called_once()


def test_database_failure_returns_controlled_server_error() -> None:
    class BrokenRepository:
        def get(self, video_id: str, language: str | None = None):
            raise TranscriptDatabaseError("database unavailable")

    with pytest.raises(TranscriptDatabaseError):
        TranscriptService(transcript_api=object(), transcript_repository=BrokenRepository()).get_transcript(VIDEO_ID)


def test_database_failure_route_does_not_expose_internal_error() -> None:
    service = TranscriptService(
        transcript_api=object(),
        transcript_repository=type(
            "BrokenRepository",
            (),
            {"get": lambda self, video_id, language=None: (_ for _ in ()).throw(TranscriptDatabaseError("secret"))},
        )(),
    )
    with patch("app.api.videos.TranscriptService", return_value=service):
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 500
    assert response.json()["detail"] == "Transcript persistence failed."
    assert "secret" not in response.text


class StubProvider(TranscriptProvider):
    def __init__(self, name: str, outcome):
        self.name = name
        self.outcome = outcome
        self.calls = 0

    def get_transcript(self, video_id: str, language: str | None = None):
        self.calls += 1
        if isinstance(self.outcome, list):
            outcome = self.outcome.pop(0)
        else:
            outcome = self.outcome
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_primary_failure_uses_authorized_fallback() -> None:
    blocked = type("IpBlocked", (Exception,), {})
    primary = StubProvider("youtube", blocked("blocked"))
    fallback_transcript = FakeTranscript("en", True, [{"text": "Fallback worked", "start": 0.0, "duration": 1.0}])
    fallback = StubProvider("authorized_fallback", (fallback_transcript, [SimpleNamespace(text="Fallback worked", start=0.0, duration=1.0)]))

    response = TranscriptService(
        provider=primary,
        fallback_provider=fallback,
        settings=Settings(transcript_max_retries=1),
    ).get_transcript(VIDEO_ID)

    assert response.segments[0].text == "Fallback worked"
    assert primary.calls == 1
    assert fallback.calls == 1


def test_both_provider_failures_return_recoverable_error() -> None:
    primary = StubProvider("youtube", RuntimeError("primary unavailable"))
    fallback = StubProvider("authorized_fallback", RuntimeError("fallback unavailable"))

    with pytest.raises(Exception) as raised:
        TranscriptService(
            provider=primary,
            fallback_provider=fallback,
            settings=Settings(transcript_max_retries=1),
        ).get_transcript(VIDEO_ID)

    assert raised.value.error_code == "PROVIDER_UNKNOWN_ERROR"
    assert raised.value.provider_name == "authorized_fallback"


def test_circuit_breaker_opens_for_ip_block_and_recovers_after_cooldown() -> None:
    blocked = type("IpBlocked", (Exception,), {})
    fallback_transcript = FakeTranscript("en", True, [{"text": "Recovered", "start": 0.0, "duration": 1.0}])
    primary = StubProvider("youtube", [blocked("blocked"), (fallback_transcript, [SimpleNamespace(text="Recovered", start=0.0, duration=1.0)])])
    service = TranscriptService(
        provider=primary,
        settings=Settings(
            transcript_max_retries=1,
            transcript_circuit_failure_threshold=1,
            transcript_circuit_cooldown_seconds=0.01,
        ),
    )

    with pytest.raises(Exception):
        service.get_transcript(VIDEO_ID)
    assert service.get_circuit_states()["youtube"] == "open"

    import time
    time.sleep(0.02)
    response = service.get_transcript(VIDEO_ID)

    assert response.segments[0].text == "Recovered"
    assert service.get_circuit_states()["youtube"] == "closed"


def test_http_fallback_provider_posts_authorized_request_and_parses_segments() -> None:
    provider = AuthorizedHttpTranscriptProvider(
        "https://transcripts.example/api/transcript",
        "fallback-secret",
        5.0,
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "language_code": "en",
        "is_generated": True,
        "segments": [{"text": "Authorized", "start": 1.0, "duration": 2.0}],
    }

    with patch("app.services.transcript.transcript_service.requests.post", return_value=response) as post:
        transcript, snippets = provider.get_transcript(VIDEO_ID, "en")

    assert transcript.language_code == "en"
    assert snippets[0].text == "Authorized"
    post.assert_called_once()
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer fallback-secret"


def test_expired_persistent_transcript_is_refetched() -> None:
    repository = TranscriptRepository(database_module.get_session_factory())
    repository.upsert(
        {
            "video_id": VIDEO_ID,
            "language_code": "en",
            "language_name": "English",
            "is_generated": False,
            "segments": [{"text": "Old cache", "start": 0.0, "duration": 1.0}],
        }
    )
    with database_module.get_session_factory()() as session:
        stored = session.query(Transcript).one()
        stored.updated_at = datetime.utcnow() - timedelta(hours=25)
        session.commit()

    transcript = FakeTranscript("en", True, [{"text": "Fresh", "start": 0.0, "duration": 1.0}])
    api = MagicMock()
    api.fetch.return_value = transcript

    response = TranscriptService(
        transcript_api=api,
        transcript_repository=repository,
        settings=Settings(transcript_cache_ttl_hours=24),
    ).get_transcript(VIDEO_ID)

    assert response.segments[0].text == "Fresh"
    api.fetch.assert_called_once()