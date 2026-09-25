import re

from fastapi import APIRouter, HTTPException, Query

from app.repositories.transcript_repository import TranscriptDatabaseError
from app.schemas.transcript import TranscriptResponse
from app.services.transcript.transcript_service import (
    TranscriptNotAvailableError,
    TranscriptProviderError,
    TranscriptService,
    VideoUnavailableError,
)

router = APIRouter(prefix="/api/videos", tags=["videos"])
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


@router.get("/{video_id}/transcript", response_model=TranscriptResponse)
def get_video_transcript(video_id: str, language: str | None = Query(default=None, min_length=2, max_length=16)) -> TranscriptResponse:
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise HTTPException(status_code=422, detail="Invalid YouTube video ID.")

    try:
        return TranscriptService().get_transcript(video_id, language)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (TranscriptNotAvailableError, VideoUnavailableError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TranscriptDatabaseError as error:
        raise HTTPException(status_code=500, detail="Transcript persistence failed.") from error
    except TranscriptProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error