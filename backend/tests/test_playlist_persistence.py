from __future__ import annotations

import importlib
import os
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.config as config_module
import app.db.database as database_module
import app.main as main_module
from app.db.base import Base
from app.models.playlist import Playlist
from app.models.video import Video
from app.repositories.playlist_repository import PlaylistRepository


def build_playlist_payload() -> dict:
    return {
        "playlist_id": "PL_TEST_123",
        "title": "Test Playlist",
        "description": "A playlist for persistence tests.",
        "thumbnail": "https://example.com/playlist.jpg",
        "channel_id": "channel_123",
        "channel_title": "Example Channel",
        "published_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }


def build_video_payloads() -> list[dict]:
    return [
        {
            "video_id": "video_1",
            "playlist_id": "PL_TEST_123",
            "title": "First video",
            "description": "First description",
            "thumbnail": "https://example.com/v1.jpg",
            "position": 0,
            "published_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "video_url": "https://www.youtube.com/watch?v=video_1",
            "duration": "PT1M30S",
            "available": True,
        },
        {
            "video_id": "video_2",
            "playlist_id": "PL_TEST_123",
            "title": "Second video",
            "description": "Second description",
            "thumbnail": "https://example.com/v2.jpg",
            "position": 1,
            "published_at": datetime(2024, 1, 3, tzinfo=timezone.utc),
            "video_url": "https://www.youtube.com/watch?v=video_2",
            "duration": "PT2M15S",
            "available": True,
        },
    ]


def make_repository() -> PlaylistRepository:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return PlaylistRepository(session_factory=session_factory)


def test_create_playlist_persists_metadata() -> None:
    repository = make_repository()

    repository.upsert_playlist(build_playlist_payload())

    stored = repository.get_playlist("PL_TEST_123")
    assert stored is not None
    assert stored.playlist_id == "PL_TEST_123"
    assert stored.title == "Test Playlist"
    assert stored.channel_title == "Example Channel"


def test_create_videos_persists_relationship_and_positions() -> None:
    repository = make_repository()
    repository.upsert_playlist(build_playlist_payload())

    repository.upsert_videos("PL_TEST_123", build_video_payloads())

    stored_videos = repository.get_playlist_videos("PL_TEST_123")
    assert [video.video_id for video in stored_videos] == ["video_1", "video_2"]
    assert [video.position for video in stored_videos] == [0, 1]

    session_factory = repository.session_factory
    with session_factory() as session:
        playlist = session.query(Playlist).filter_by(playlist_id="PL_TEST_123").one()
        assert len(playlist.videos) == 2
        assert {video.video_id for video in playlist.videos} == {"video_1", "video_2"}


def test_idempotent_playlist_insert_updates_in_place() -> None:
    repository = make_repository()

    repository.upsert_playlist(build_playlist_payload())
    repository.upsert_playlist({**build_playlist_payload(), "title": "Updated Playlist Title"})

    with repository.session_factory() as session:
        assert session.query(Playlist).count() == 1
        stored = session.query(Playlist).filter_by(playlist_id="PL_TEST_123").one()
        assert stored.title == "Updated Playlist Title"


def test_idempotent_video_insert_does_not_duplicate_rows() -> None:
    repository = make_repository()
    repository.upsert_playlist(build_playlist_payload())

    payload = build_video_payloads()
    repository.upsert_videos("PL_TEST_123", payload)
    repository.upsert_videos("PL_TEST_123", payload)

    with repository.session_factory() as session:
        assert session.query(Video).count() == 2
        assert session.query(Video).filter_by(playlist_id="PL_TEST_123").count() == 2


def test_metadata_update_persists_changes() -> None:
    repository = make_repository()
    repository.upsert_playlist(build_playlist_payload())

    updated = {**build_playlist_payload(), "title": "Refreshed playlist", "description": "Updated description"}
    repository.upsert_playlist(updated)

    stored = repository.get_playlist("PL_TEST_123")
    assert stored is not None
    assert stored.title == "Refreshed playlist"
    assert stored.description == "Updated description"


def test_new_video_inserted_during_refresh() -> None:
    repository = make_repository()
    repository.upsert_playlist(build_playlist_payload())
    repository.upsert_videos("PL_TEST_123", build_video_payloads())

    refreshed = [{
        "video_id": "video_3",
        "playlist_id": "PL_TEST_123",
        "title": "Third video",
        "description": "Third description",
        "thumbnail": "https://example.com/v3.jpg",
        "position": 2,
        "published_at": datetime(2024, 1, 4, tzinfo=timezone.utc),
        "video_url": "https://www.youtube.com/watch?v=video_3",
        "duration": "PT3M45S",
        "available": True,
    }]
    repository.upsert_videos("PL_TEST_123", build_video_payloads() + refreshed)

    stored = repository.get_playlist_videos("PL_TEST_123")
    assert [video.video_id for video in stored] == ["video_1", "video_2", "video_3"]


def test_ordering_is_preserved_when_retrieving_videos() -> None:
    repository = make_repository()
    repository.upsert_playlist(build_playlist_payload())

    ordered = [
        {
            "video_id": "video_b",
            "playlist_id": "PL_TEST_123",
            "title": "B",
            "description": "B",
            "thumbnail": "https://example.com/b.jpg",
            "position": 2,
            "published_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "video_url": "https://www.youtube.com/watch?v=video_b",
            "duration": "PT1M",
            "available": True,
        },
        {
            "video_id": "video_a",
            "playlist_id": "PL_TEST_123",
            "title": "A",
            "description": "A",
            "thumbnail": "https://example.com/a.jpg",
            "position": 0,
            "published_at": datetime(2024, 1, 3, tzinfo=timezone.utc),
            "video_url": "https://www.youtube.com/watch?v=video_a",
            "duration": "PT2M",
            "available": True,
        },
    ]
    repository.upsert_videos("PL_TEST_123", ordered)

    stored = repository.get_playlist_videos("PL_TEST_123")
    assert [video.position for video in stored] == [0, 2]
    assert [video.video_id for video in stored] == ["video_a", "video_b"]


def test_transaction_failure_does_not_leave_partial_dataset() -> None:
    repository = make_repository()
    repository.upsert_playlist(build_playlist_payload())

    try:
        repository.upsert_videos("PL_TEST_123", [{**build_video_payloads()[0], "video_id": None}])
    except ValueError:
        pass

    with repository.session_factory() as session:
        assert session.query(Video).count() == 0


def build_stored_playlist_client() -> TestClient:
    os.environ["DATABASE_URL"] = "sqlite://"
    os.environ["YOUTUBE_API_KEY"] = "test-key"
    config_module.get_settings.cache_clear()
    importlib.reload(database_module)
    database_module.engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    database_module.SessionLocal = sessionmaker(
        bind=database_module.engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    database_module.Base.metadata.create_all(bind=database_module.engine)
    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_stored_playlist_route_returns_playlist_and_videos() -> None:
    client = build_stored_playlist_client()
    repository = PlaylistRepository(database_module.get_session_factory())
    repository.upsert_playlist(build_playlist_payload())
    repository.upsert_videos("PL_TEST_123", build_video_payloads())

    response = client.get("/api/playlists/PL_TEST_123/stored")

    assert response.status_code == 200
    payload = response.json()
    assert payload["playlist"]["playlist_id"] == "PL_TEST_123"
    assert payload["playlist"]["title"] == "Test Playlist"
    assert payload["total_videos"] == 2
    assert [video["video_id"] for video in payload["videos"]] == ["video_1", "video_2"]


def test_stored_playlist_route_orders_videos_by_position() -> None:
    client = build_stored_playlist_client()
    repository = PlaylistRepository(database_module.get_session_factory())
    repository.upsert_playlist(build_playlist_payload())
    repository.upsert_videos(
        "PL_TEST_123",
        [
            {
                "video_id": "video_2",
                "playlist_id": "PL_TEST_123",
                "title": "Second",
                "description": "Second description",
                "thumbnail": "https://example.com/v2.jpg",
                "position": 2,
                "published_at": datetime(2024, 1, 3, tzinfo=timezone.utc),
                "video_url": "https://www.youtube.com/watch?v=video_2",
                "duration": "PT2M",
                "available": True,
            },
            {
                "video_id": "video_0",
                "playlist_id": "PL_TEST_123",
                "title": "First",
                "description": "First description",
                "thumbnail": "https://example.com/v0.jpg",
                "position": 0,
                "published_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "video_url": "https://www.youtube.com/watch?v=video_0",
                "duration": "PT1M",
                "available": True,
            },
            {
                "video_id": "video_1",
                "playlist_id": "PL_TEST_123",
                "title": "Middle",
                "description": "Middle description",
                "thumbnail": "https://example.com/v1.jpg",
                "position": 1,
                "published_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
                "video_url": "https://www.youtube.com/watch?v=video_1",
                "duration": "PT90S",
                "available": True,
            },
        ],
    )

    response = client.get("/api/playlists/PL_TEST_123/stored")

    assert response.status_code == 200
    assert [video["position"] for video in response.json()["videos"]] == [0, 1, 2]
    assert [video["video_id"] for video in response.json()["videos"]] == ["video_0", "video_1", "video_2"]


def test_stored_playlist_route_returns_404_for_missing_playlist() -> None:
    client = build_stored_playlist_client()

    response = client.get("/api/playlists/NOT_HERE/stored")

    assert response.status_code == 404
    assert response.json()["detail"] == "Playlist has not been indexed yet."


def test_stored_playlist_route_does_not_call_youtube() -> None:
    client = build_stored_playlist_client()
    repository = PlaylistRepository(database_module.get_session_factory())
    repository.upsert_playlist(build_playlist_payload())
    repository.upsert_videos("PL_TEST_123", build_video_payloads())

    with patch("app.services.playlist_service.YouTubePlaylistService.get_playlist") as mock_get_playlist:
        response = client.get("/api/playlists/PL_TEST_123/stored")

    assert response.status_code == 200
    mock_get_playlist.assert_not_called()


def test_stored_playlist_route_handles_empty_playlist() -> None:
    client = build_stored_playlist_client()
    repository = PlaylistRepository(database_module.get_session_factory())
    repository.upsert_playlist(build_playlist_payload())

    response = client.get("/api/playlists/PL_TEST_123/stored")

    assert response.status_code == 200
    payload = response.json()
    assert payload["playlist"]["playlist_id"] == "PL_TEST_123"
    assert payload["videos"] == []
    assert payload["total_videos"] == 0
