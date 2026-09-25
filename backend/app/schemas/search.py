from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: StrictStr
    top_k: StrictInt | None = Field(default=None, gt=0)
    video_id: StrictStr | None = None
    score_threshold: StrictFloat | None = Field(default=None, ge=-1, le=1)


class SearchResult(BaseModel):
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


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    result_count: int