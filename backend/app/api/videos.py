import re

from fastapi import APIRouter, HTTPException, Query

from app.repositories.transcript_repository import TranscriptDatabaseError, TranscriptRepository
from app.schemas.chunk import TranscriptChunkResponse
from app.schemas.embedding import ChunkEmbedding, VideoEmbeddingResponse
from app.schemas.transcript import TranscriptResponse
from app.services.embedding_service import EmbeddingModelError, EmbeddingService
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


@router.post("/{video_id}/embeddings", response_model=VideoEmbeddingResponse)
def generate_video_embeddings(
    video_id: str, language: str | None = Query(default=None, min_length=2, max_length=16)
) -> VideoEmbeddingResponse:
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise HTTPException(status_code=422, detail="Invalid YouTube video ID.")

    repository = TranscriptRepository()
    try:
        chunks = repository.get_chunks(video_id, language)
        if not chunks:
            raise HTTPException(status_code=404, detail="No stored transcript chunks were found.")
        service = EmbeddingService()
        pending = [
            chunk for chunk in chunks
            if chunk.embedding is None or chunk.embedding_model != service.model_name
        ]
        generated = service.embed_chunks(pending)
        dimension = len(generated[0].vector) if generated else chunks[0].embedding_dimension
        if dimension is None:
            raise EmbeddingModelError("Stored embedding metadata is incomplete.")
        repository.save_embeddings(
            {item.chunk_id: item.vector for item in generated}, service.model_name, dimension
        )
        generated_by_id = {item.chunk_id: item.vector for item in generated}
        embeddings = [
            ChunkEmbedding(
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                embedding=generated_by_id.get(chunk.id) or service.decode_vector(chunk.embedding) or [],
            )
            for chunk in chunks
        ]
        return VideoEmbeddingResponse(
            video_id=video_id,
            language_code=chunks[0].language_code,
            model=service.model_name,
            dimension=dimension,
            total_chunks=len(chunks),
            generated_chunks=len(generated),
            reused_chunks=len(chunks) - len(generated),
            embeddings=embeddings,
        )
    except HTTPException:
        raise
    except (TranscriptDatabaseError, EmbeddingModelError) as error:
        raise HTTPException(status_code=500, detail="Embedding generation failed.") from error


@router.get("/{video_id}/chunks", response_model=TranscriptChunkResponse)
def get_video_chunks(video_id: str, language: str | None = Query(default=None, min_length=2, max_length=16)) -> TranscriptChunkResponse:
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise HTTPException(status_code=422, detail="Invalid YouTube video ID.")

    from app.services.transcript.chunk_service import TranscriptChunkService

    try:
        return TranscriptChunkService().get_chunks(video_id, language)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except TranscriptNotAvailableError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TranscriptDatabaseError as error:
        raise HTTPException(status_code=500, detail="Transcript persistence failed.") from error