import re

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.db.database import DatabaseConfigurationError
from app.schemas.playlist import PlaylistResponse
from app.services.playlist_service import PlaylistService
from app.services.youtube.playlist_service import YouTubeServiceError

router = APIRouter(prefix="/api/playlists", tags=["playlists"])
PLAYLIST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@router.get("/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(playlist_id: str) -> PlaylistResponse:
    if not PLAYLIST_ID_PATTERN.fullmatch(playlist_id):
        raise HTTPException(status_code=422, detail="Invalid YouTube playlist ID.")
    service = PlaylistService(get_settings())
    try:
        return await service.get_playlist(playlist_id)
    except (DatabaseConfigurationError, ValueError) as error:
        raise HTTPException(
            status_code=503,
            detail="Playlist persistence is unavailable. Configure DATABASE_URL before retrying.",
        ) from error
    except YouTubeServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error