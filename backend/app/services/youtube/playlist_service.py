from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.playlist import PlaylistMetadata, PlaylistResponse, PlaylistVideo


class YouTubeServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class YouTubePlaylistService:
    base_url = "https://www.googleapis.com/youtube/v3"

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.youtube_api_key

    async def get_playlist(self, playlist_id: str) -> PlaylistResponse:
        if not self.api_key:
            raise YouTubeServiceError("YouTube API key is not configured.", 503)

        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            playlist_item = await self._get_playlist_item(client, playlist_id)
            if playlist_item is None:
                raise YouTubeServiceError("Playlist was not found.", 404)

            items = await self._get_all_playlist_items(client, playlist_id)
            video_details = await self._get_video_details(client, [
                item.get("contentDetails", {}).get("videoId") for item in items
            ])

        snippet = playlist_item.get("snippet", {})
        return PlaylistResponse(
            playlist=PlaylistMetadata(
                playlist_id=playlist_id,
                title=snippet.get("title", "Untitled playlist"),
                description=snippet.get("description", ""),
                thumbnail=self._thumbnail(snippet.get("thumbnails")),
                channel_id=snippet.get("channelId"),
                channel_title=snippet.get("channelTitle"),
                published_at=snippet.get("publishedAt"),
            ),
            videos=[self._video_model(item, video_details) for item in items if item.get("contentDetails", {}).get("videoId")],
        )

    async def _get_playlist_item(self, client: httpx.AsyncClient, playlist_id: str) -> dict[str, Any] | None:
        data = await self._request(client, "playlists", {"part": "snippet", "id": playlist_id})
        return data.get("items", [None])[0]

    async def _get_all_playlist_items(self, client: httpx.AsyncClient, playlist_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            params: dict[str, str | int] = {"part": "snippet,contentDetails", "playlistId": playlist_id, "maxResults": 50}
            if page_token:
                params["pageToken"] = page_token
            data = await self._request(client, "playlistItems", params)
            items.extend(data.get("items", []))
            next_token = data.get("nextPageToken")
            if not next_token or next_token in seen_tokens:
                return items
            seen_tokens.add(next_token)
            page_token = next_token

    async def _get_video_details(self, client: httpx.AsyncClient, video_ids: list[str | None]) -> dict[str, dict[str, Any]]:
        details: dict[str, dict[str, Any]] = {}
        valid_ids = [video_id for video_id in video_ids if video_id]
        for start in range(0, len(valid_ids), 50):
            data = await self._request(client, "videos", {"part": "snippet,contentDetails", "id": ",".join(valid_ids[start:start + 50])})
            for item in data.get("items", []):
                details[item["id"]] = item
        return details

    async def _request(self, client: httpx.AsyncClient, resource: str, params: dict[str, str | int]) -> dict[str, Any]:
        try:
            response = await client.get(f"/{resource}", params={**params, "key": self.api_key})
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise YouTubeServiceError("YouTube resource was not found.", 404) from error
            raise YouTubeServiceError("YouTube API request failed.") from error
        except httpx.HTTPError as error:
            raise YouTubeServiceError("YouTube API request failed.") from error
        return response.json()

    @staticmethod
    def _thumbnail(thumbnails: dict[str, Any] | None) -> str | None:
        if not thumbnails:
            return None
        return next((thumbnails[key]["url"] for key in ("maxres", "standard", "high", "medium", "default") if key in thumbnails), None)

    @classmethod
    def _video_model(cls, item: dict[str, Any], details: dict[str, dict[str, Any]]) -> PlaylistVideo:
        item_snippet = item.get("snippet", {})
        content = item.get("contentDetails", {})
        video_id = content["videoId"]
        video = details.get(video_id, {})
        video_snippet = video.get("snippet", {})
        return PlaylistVideo(
            video_id=video_id,
            title=item_snippet.get("title", "Untitled video"),
            description=item_snippet.get("description", ""),
            thumbnail=cls._thumbnail(item_snippet.get("thumbnails")),
            position=item_snippet.get("position", 0),
            published_at=video_snippet.get("publishedAt") or item_snippet.get("publishedAt"),
            video_url=f"https://www.youtube.com/watch?v={video_id}",
            duration=video.get("contentDetails", {}).get("duration"),
        )