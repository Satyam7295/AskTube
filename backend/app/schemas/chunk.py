from pydantic import BaseModel


class TranscriptChunk(BaseModel):
    video_id: str
    language_code: str
    chunk_index: int
    text: str
    start_time: float
    end_time: float
    segment_start_index: int
    segment_end_index: int
    character_count: int
    word_count: int


class TranscriptChunkResponse(BaseModel):
    video_id: str
    language_code: str
    chunks: list[TranscriptChunk]
    total_chunks: int