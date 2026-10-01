from __future__ import annotations

from app.repositories.transcript_repository import TranscriptRepository
from app.schemas.chunk import TranscriptChunk, TranscriptChunkResponse
from app.services.transcript.chunker import TranscriptChunker
from app.services.transcript.transcript_service import TranscriptNotAvailableError, TranscriptService


class TranscriptChunkService:
    def __init__(self, transcript_repository=None, chunker: TranscriptChunker | None = None) -> None:
        self.transcript_repository = transcript_repository or TranscriptRepository()
        self.chunker = chunker or TranscriptChunker()

    def get_chunks(self, video_id: str, language: str | None = None, playlist_id: str | None = None) -> TranscriptChunkResponse:
        TranscriptService._validate_video_id(video_id)
        stored = self.transcript_repository.get(video_id, language)
        if stored is None:
            raise TranscriptNotAvailableError("Transcript is not available for this video.")

        language_code = stored.language_code
        playlist_id = playlist_id or getattr(self.transcript_repository, "get_video_playlist_id", lambda _video_id: None)(video_id)
        generated = self.chunker.chunk(video_id, language_code, stored.segments, playlist_id)
        try:
            persisted = self.transcript_repository.replace_chunks(video_id, language_code, generated, playlist_id)
        except TypeError:
            persisted = self.transcript_repository.replace_chunks(video_id, language_code, generated)
        chunks = [TranscriptChunk.model_validate(chunk, from_attributes=True) for chunk in persisted]
        return TranscriptChunkResponse(
            video_id=video_id,
            language_code=language_code,
            chunks=chunks,
            total_chunks=len(chunks),
        )