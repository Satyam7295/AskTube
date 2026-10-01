import asyncio
from unittest.mock import AsyncMock

from app.core.config import Settings
from app.services.youtube.playlist_service import YouTubePlaylistService


def test_empty_youtube_playlist_response_returns_none() -> None:
    service = YouTubePlaylistService(Settings(youtube_api_key="test-key"))
    service._request = AsyncMock(return_value={"items": []})

    result = asyncio.run(service._get_playlist_item(object(), "PL_missing"))

    assert result is None