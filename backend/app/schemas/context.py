from pydantic import BaseModel, ConfigDict


class RetrievedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    video_id: str
    score: float
    text: str
    start_time: float
    end_time: float
    chunk_index: int
    language_code: str | None = None
    segment_start_index: int | None = None
    segment_end_index: int | None = None
    character_count: int | None = None
    word_count: int | None = None


class RAGContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    sources: list[RetrievedSource]
    context_text: str
    source_count: int
    total_characters: int
    total_words: int