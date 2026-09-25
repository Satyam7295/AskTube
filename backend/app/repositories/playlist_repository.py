from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.db.database import DatabaseConfigurationError, get_session_factory
from app.models.playlist import Playlist
from app.models.video import Video


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


class PlaylistRepository:
    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or get_session_factory()

    def get_playlist(self, playlist_id: str) -> Playlist | None:
        with self.session_factory() as session:
            return session.query(Playlist).filter(Playlist.playlist_id == playlist_id).one_or_none()

    def upsert_playlist(self, playlist_data: dict[str, Any]) -> Playlist:
        playlist_id = playlist_data["playlist_id"]
        with self.session_factory() as session:
            with session.begin():
                playlist = session.query(Playlist).filter(Playlist.playlist_id == playlist_id).one_or_none()
                if playlist is None:
                    playlist = Playlist(
                        playlist_id=playlist_id,
                        title=playlist_data.get("title", "Untitled playlist"),
                        description=playlist_data.get("description"),
                        thumbnail=playlist_data.get("thumbnail"),
                        channel_id=playlist_data.get("channel_id"),
                        channel_title=playlist_data.get("channel_title"),
                        published_at=_coerce_datetime(playlist_data.get("published_at")),
                    )
                    session.add(playlist)
                else:
                    playlist.title = playlist_data.get("title", playlist.title)
                    playlist.description = playlist_data.get("description", playlist.description)
                    playlist.thumbnail = playlist_data.get("thumbnail", playlist.thumbnail)
                    playlist.channel_id = playlist_data.get("channel_id", playlist.channel_id)
                    playlist.channel_title = playlist_data.get("channel_title", playlist.channel_title)
                    playlist.published_at = _coerce_datetime(playlist_data.get("published_at", playlist.published_at))
                    playlist.updated_at = datetime.utcnow()
                session.flush()
                return playlist

    def upsert_videos(self, playlist_id: str, videos: list[dict[str, Any]]) -> list[Video]:
        if not videos:
            return []

        with self.session_factory() as session:
            with session.begin():
                playlist = session.query(Playlist).filter(Playlist.playlist_id == playlist_id).one_or_none()
                if playlist is None:
                    raise DatabaseConfigurationError(
                        f"Cannot persist videos for unknown playlist '{playlist_id}'. Save the playlist first."
                    )

                existing = {
                    video.video_id: video
                    for video in session.query(Video).filter(Video.playlist_id == playlist_id).all()
                }

                saved: list[Video] = []
                for payload in videos:
                    video_id = payload.get("video_id")
                    if not video_id:
                        raise ValueError("Video payload is missing a video_id.")

                    if video_id in existing:
                        video = existing[video_id]
                        video.title = payload.get("title", video.title)
                        video.description = payload.get("description", video.description)
                        video.thumbnail = payload.get("thumbnail", video.thumbnail)
                        video.position = int(payload.get("position", video.position))
                        video.published_at = _coerce_datetime(payload.get("published_at", video.published_at))
                        video.video_url = payload.get("video_url", video.video_url)
                        video.duration = payload.get("duration", video.duration)
                        video.available = bool(payload.get("available", video.available))
                        video.updated_at = datetime.utcnow()
                        saved.append(video)
                    else:
                        video = Video(
                            video_id=video_id,
                            playlist_id=playlist_id,
                            title=payload.get("title", "Untitled video"),
                            description=payload.get("description"),
                            thumbnail=payload.get("thumbnail"),
                            position=int(payload.get("position", 0)),
                            published_at=_coerce_datetime(payload.get("published_at")),
                            video_url=payload.get("video_url", f"https://www.youtube.com/watch?v={video_id}"),
                            duration=payload.get("duration"),
                            available=bool(payload.get("available", True)),
                        )
                        session.add(video)
                        existing[video_id] = video
                        saved.append(video)

                session.flush()
                return saved

    def upsert_playlist_with_videos(self, playlist_data: dict[str, Any], videos: list[dict[str, Any]]) -> Playlist:
        playlist_id = playlist_data["playlist_id"]

        with self.session_factory() as session:
            with session.begin():
                playlist = session.query(Playlist).filter(Playlist.playlist_id == playlist_id).one_or_none()
                if playlist is None:
                    playlist = Playlist(
                        playlist_id=playlist_id,
                        title=playlist_data.get("title", "Untitled playlist"),
                        description=playlist_data.get("description"),
                        thumbnail=playlist_data.get("thumbnail"),
                        channel_id=playlist_data.get("channel_id"),
                        channel_title=playlist_data.get("channel_title"),
                        published_at=_coerce_datetime(playlist_data.get("published_at")),
                    )
                    session.add(playlist)
                else:
                    playlist.title = playlist_data.get("title", playlist.title)
                    playlist.description = playlist_data.get("description", playlist.description)
                    playlist.thumbnail = playlist_data.get("thumbnail", playlist.thumbnail)
                    playlist.channel_id = playlist_data.get("channel_id", playlist.channel_id)
                    playlist.channel_title = playlist_data.get("channel_title", playlist.channel_title)
                    playlist.published_at = _coerce_datetime(playlist_data.get("published_at", playlist.published_at))
                    playlist.updated_at = datetime.utcnow()

                existing = {
                    video.video_id: video
                    for video in session.query(Video).filter(Video.playlist_id == playlist_id).all()
                }

                for payload in videos:
                    video_id = payload.get("video_id")
                    if not video_id:
                        raise ValueError("Video payload is missing a video_id.")

                    if video_id in existing:
                        video = existing[video_id]
                        video.title = payload.get("title", video.title)
                        video.description = payload.get("description", video.description)
                        video.thumbnail = payload.get("thumbnail", video.thumbnail)
                        video.position = int(payload.get("position", video.position))
                        video.published_at = _coerce_datetime(payload.get("published_at", video.published_at))
                        video.video_url = payload.get("video_url", video.video_url)
                        video.duration = payload.get("duration", video.duration)
                        video.available = bool(payload.get("available", video.available))
                        video.updated_at = datetime.utcnow()
                        existing[video_id] = video
                    else:
                        video = Video(
                            video_id=video_id,
                            playlist_id=playlist_id,
                            title=payload.get("title", "Untitled video"),
                            description=payload.get("description"),
                            thumbnail=payload.get("thumbnail"),
                            position=int(payload.get("position", 0)),
                            published_at=_coerce_datetime(payload.get("published_at")),
                            video_url=payload.get("video_url", f"https://www.youtube.com/watch?v={video_id}"),
                            duration=payload.get("duration"),
                            available=bool(payload.get("available", True)),
                        )
                        session.add(video)
                        existing[video_id] = video

                session.flush()
                return playlist

    def get_playlist_videos(self, playlist_id: str) -> list[Video]:
        with self.session_factory() as session:
            return (
                session.query(Video)
                .filter(Video.playlist_id == playlist_id)
                .order_by(Video.position.asc(), Video.video_id.asc())
                .all()
            )
