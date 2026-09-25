from fastapi import APIRouter, HTTPException

from app.schemas.answer import AskResponse
from app.schemas.search import SearchRequest
from app.services.context_builder import ContextBuilder, ContextBuilderInputError
from app.services.embedding_service import EmbeddingModelError
from app.services.llm_service import LLMConfigurationError, LLMResponseError, LLMService, LLMProviderError
from app.services.qdrant_service import QdrantConfigurationError, QdrantSearchError
from app.services.retrieval_service import RetrievalInputError, RetrievalResultError, RetrievalService

router = APIRouter(prefix="/api/ask", tags=["ask"])


@router.post("", response_model=AskResponse)
def ask_question(request: SearchRequest) -> AskResponse:
    try:
        query, results = RetrievalService().retrieve(
            request.query, request.top_k, request.video_id, request.score_threshold
        )
        context = ContextBuilder().build(query, results)
        answer = LLMService().generate_answer(context)
        return AskResponse(
            query=query,
            answer=answer.answer,
            sources=context.sources,
            provider=answer.provider,
            model=answer.model,
            insufficient_context=answer.insufficient_context,
        )
    except RetrievalInputError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ContextBuilderInputError as error:
        raise HTTPException(status_code=502, detail="Transcript context could not be built.") from error
    except RetrievalResultError as error:
        raise HTTPException(status_code=502, detail="Qdrant returned invalid transcript metadata.") from error
    except EmbeddingModelError as error:
        raise HTTPException(status_code=502, detail="Query embedding generation failed.") from error
    except (QdrantConfigurationError, QdrantSearchError) as error:
        raise HTTPException(status_code=503, detail="Semantic search service is unavailable.") from error
    except LLMConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (LLMProviderError, LLMResponseError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error