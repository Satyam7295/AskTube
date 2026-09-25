from __future__ import annotations

from app.core.config import Settings
from app.repositories.playlist_repository import PlaylistRepository
from app.schemas.playlist import PlaylistMetadata, PlaylistResponse, PlaylistVideo
from app.services.youtube.playlist_service import YouTubePlaylistService


class PlaylistServiceError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PlaylistService:
    def __init__(self, settings: Settings, repository: PlaylistRepository | None = None) -> None:
        self.settings = settings
        self.youtube_service = YouTubePlaylistService(settings)
        self.repository = repository or PlaylistRepository()

    async def get_playlist(self, playlist_id: str) -> PlaylistResponse:
        response = await self.youtube_service.get_playlist(playlist_id)
        payload = [
            {
                "video_id": video.video_id,
                "playlist_id": playlist_id,
                "title": video.title,
                "description": video.description,
                "thumbnail": str(video.thumbnail) if video.thumbnail else None,
                "position": video.position,
                "published_at": video.published_at,
                "video_url": str(video.video_url),
                "duration": video.duration,
                "available": True,
            }
            for video in response.videos
        ]
        self.repository.upsert_playlist_with_videos(
            {
                "playlist_id": response.playlist.playlist_id,
                "title": response.playlist.title,
                "description": response.playlist.description,
                "thumbnail": str(response.playlist.thumbnail) if response.playlist.thumbnail else None,
                "channel_id": response.playlist.channel_id,
                "channel_title": response.playlist.channel_title,
                "published_at": response.playlist.published_at,
            },
            payload,
        )
        return response

    def get_persisted_playlist(self, playlist_id: str) -> PlaylistResponse | None:
        playlist = self.repository.get_playlist(playlist_id)
        if playlist is None:
            return None

        videos = self.repository.get_playlist_videos(playlist_id)
        return PlaylistResponse(
            playlist=PlaylistMetadata(
                playlist_id=playlist.playlist_id,
                title=playlist.title,
                description=playlist.description or "",
                thumbnail=self._to_http_url(playlist.thumbnail),
                channel_id=playlist.channel_id,
                channel_title=playlist.channel_title,
                published_at=playlist.published_at,
            ),
            videos=[
                PlaylistVideo(
                    video_id=video.video_id,
                    title=video.title,
                    description=video.description or "",
                    thumbnail=self._to_http_url(video.thumbnail),
                    position=video.position,
                    published_at=video.published_at,
                    video_url=video.video_url,
                    duration=video.duration,
                )
                for video in videos
            ],
        )

    @staticmethod
    def _to_http_url(value: str | None):
        if not value:
            return None
        return value
