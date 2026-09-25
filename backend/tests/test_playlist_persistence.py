from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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
