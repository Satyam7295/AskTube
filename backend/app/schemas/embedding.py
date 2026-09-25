from pydantic import BaseModel


class ChunkEmbedding(BaseModel):
    chunk_id: int
    chunk_index: int
    embedding: list[float]


class VideoEmbeddingResponse(BaseModel):
    video_id: str
    language_code: str
    model: str
    dimension: int
    total_chunks: int
    generated_chunks: int
    reused_chunks: int
    embeddings: list[ChunkEmbedding]


class VectorSyncResponse(BaseModel):
    video_id: str
    language_code: str
    collection: str
    total_chunks: int
    upserted: int
    skipped: int