import re

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.playlist import PlaylistResponse
from app.services.youtube.playlist_service import YouTubePlaylistService, YouTubeServiceError

router = APIRouter(prefix="/api/playlists", tags=["playlists"])
PLAYLIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@router.get("/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(playlist_id: str) -> PlaylistResponse:
    if not PLAYLIST_ID_PATTERN.fullmatch(playlist_id):
        raise HTTPException(status_code=422, detail="Invalid YouTube playlist ID.")
    try:
        return await YouTubePlaylistService(get_settings()).get_playlist(playlist_id)
    except YouTubeServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error