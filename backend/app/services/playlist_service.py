from __future__ import annotations

from app.core.config import Settings
from app.repositories.playlist_repository import PlaylistRepository
from app.schemas.playlist import PlaylistMetadata, PlaylistResponse, PlaylistVideo
from app.services.youtube.playlist_service import YouTubePlaylistService
from app.services.playlist_indexing_service import PlaylistIndexReport, PlaylistIndexingService
from fastapi import BackgroundTasks


class PlaylistServiceError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PlaylistService:
    def __init__(
        self,
        settings: Settings,
        repository: PlaylistRepository | None = None,
        indexing_service: PlaylistIndexingService | None = None,
    ) -> None:
        self.settings = settings
        self.youtube_service = YouTubePlaylistService(settings)
        self.repository = repository or PlaylistRepository()
        self.indexing_service = indexing_service or PlaylistIndexingService(settings, self.repository)

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
        response.total_videos = len(response.videos)
        report = self.indexing_service.prepare_indexing(playlist_id)
        self._apply_index_report(response, report)
        return response

    def schedule_indexing(self, playlist_id: str, background_tasks: BackgroundTasks) -> None:
        if self.indexing_service.schedule_indexing(playlist_id):
            background_tasks.add_task(self.indexing_service.run_indexing, playlist_id)

    def get_persisted_playlist(self, playlist_id: str) -> PlaylistResponse | None:
        playlist, videos = self.repository.get_playlist_with_videos(playlist_id)
        if playlist is None:
            return None

        ordered_videos = [
            PlaylistVideo(
                video_id=video.video_id,
                title=video.title,
                description=video.description or "",
                thumbnail=self._to_http_url(video.thumbnail),
                position=video.position,
                published_at=video.published_at,
                video_url=video.video_url,
                duration=video.duration,
                available=video.available,
            )
            for video in videos
        ]
        response = PlaylistResponse(
            playlist=PlaylistMetadata(
                playlist_id=playlist.playlist_id,
                title=playlist.title,
                description=playlist.description or "",
                thumbnail=self._to_http_url(playlist.thumbnail),
                channel_id=playlist.channel_id,
                channel_title=playlist.channel_title,
                published_at=playlist.published_at,
            ),
            videos=ordered_videos,
            total_videos=len(ordered_videos),
        )
        status = self.repository.get_index_status(playlist_id)
        if status is not None:
            self._apply_index_report(response, PlaylistIndexingService._report(status))
        return response

    @staticmethod
    def _apply_index_report(response: PlaylistResponse, report: PlaylistIndexReport) -> None:
        response.indexing_status = report.status
        response.processed_videos = report.processed_videos
        response.indexed_videos = report.indexed_videos
        response.skipped_videos = report.skipped_videos
        response.videos_without_transcripts = report.skipped_videos
        response.failed_videos = report.failed_videos

    @staticmethod
    def _to_http_url(value: str | None):
        if not value:
            return None
        return value
