from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.transcript.transcript_service import TranscriptService


VIDEO_ID = "dQw4w9WgXcQ"


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
        api.return_value.list.return_value = [transcript]
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
        api.return_value.list.return_value = [transcript]
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.json()["segments"] == [{"text": "A point in time", "start": 12.43, "duration": 15.38}]


def test_no_transcript_returns_not_found() -> None:
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.return_value = []
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 404
    assert response.json()["detail"] == "Transcript is not available for this video."


def test_video_unavailable_returns_not_found() -> None:
    unavailable = type("VideoUnavailable", (Exception,), {})
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.side_effect = unavailable()
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 404
    assert response.json()["detail"] == "Video was not found or is unavailable."


def test_provider_failure_returns_bad_gateway() -> None:
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.side_effect = RuntimeError("provider down")
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")

    assert response.status_code == 502
    assert response.json()["detail"] == "Transcript provider request failed."


def test_invalid_video_id_returns_validation_error() -> None:
    response = client().get("/api/videos/too-short/transcript")

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid YouTube video ID."


def test_language_selection_is_deterministic() -> None:
    spanish = FakeTranscript("es", False, [{"text": "Hola", "start": 0.0, "duration": 1.0}])
    english = FakeTranscript("en", True, [{"text": "Hello", "start": 0.0, "duration": 1.0}])
    with patch("app.services.transcript.transcript_service.YouTubeTranscriptApi") as api:
        api.return_value.list.return_value = [spanish, english]
        response = client().get(f"/api/videos/{VIDEO_ID}/transcript")
        requested = client().get(f"/api/videos/{VIDEO_ID}/transcript?language=es")

    assert response.json()["language"] == "en"
    assert requested.json()["language"] == "es"


def test_service_rejects_invalid_video_id() -> None:
    with pytest.raises(ValueError, match="Invalid YouTube video ID"):
        TranscriptService(transcript_api=object()).get_transcript("invalid")