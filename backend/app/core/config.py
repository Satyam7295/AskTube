from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AskTube API"
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3015",
    ]
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
    transcript_proxy_http: str | None = None
    transcript_proxy_https: str | None = None
    transcript_proxy_enabled: bool = False
    youtube_proxy_enabled: bool = False
    transcript_proxy_username: str | None = None
    transcript_proxy_password: str | None = None
    youtube_proxy_username: str | None = None
    youtube_proxy_password: str | None = None
    transcript_provider_timeout: float = 30.0
    transcript_max_retries: int = Field(
        default=3,
        validation_alias=AliasChoices("TRANSCRIPT_RETRY_MAX_ATTEMPTS", "transcript_max_retries"),
    )
    transcript_retry_backoff_seconds: float = Field(
        default=0.5,
        validation_alias=AliasChoices("TRANSCRIPT_RETRY_BASE_DELAY", "transcript_retry_backoff_seconds"),
    )
    transcript_request_delay_seconds: float = 0.0
    transcript_fallback_url: str | None = None
    transcript_fallback_api_key: str | None = None
    transcript_cache_ttl_hours: int = 168
    transcript_circuit_failure_threshold: int = 3
    transcript_circuit_cooldown_seconds: float = 300.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
