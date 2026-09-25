from fastapi import APIRouter, HTTPException

from app.schemas.search import SearchRequest, SearchResponse
from app.services.embedding_service import EmbeddingModelError
from app.services.qdrant_service import QdrantConfigurationError, QdrantSearchError
from app.services.retrieval_service import RetrievalInputError, RetrievalResultError, RetrievalService

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_transcript_chunks(request: SearchRequest) -> SearchResponse:
    try:
        query, results = RetrievalService().retrieve(
            request.query, request.top_k, request.video_id, request.score_threshold
        )
        return SearchResponse(query=query, results=results, result_count=len(results))
    except RetrievalInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RetrievalResultError as error:
        raise HTTPException(status_code=502, detail="Qdrant returned invalid transcript metadata.") from error
    except EmbeddingModelError as error:
        raise HTTPException(status_code=502, detail="Query embedding generation failed.") from error
    except (QdrantConfigurationError, QdrantSearchError) as error:
        raise HTTPException(status_code=503, detail="Semantic search service is unavailable.") from error