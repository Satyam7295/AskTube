from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AskTube API"
    database_url: str | None = None
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection_name: str = "asktube_chunks"
    youtube_api_key: str | None = None
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    embedding_normalize: bool = True
    embedding_batch_size: int = 32
    retrieval_top_k: int = 5
    retrieval_max_top_k: int = 100
    rag_max_context_chars: int = 12000
    rag_max_sources: int = 5
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
