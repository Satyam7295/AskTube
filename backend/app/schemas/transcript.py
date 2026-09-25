from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    text: str
    start: float
    duration: float


class TranscriptResponse(BaseModel):
    video_id: str
    language: str | None = None
    is_generated: bool | None = None
    segments: list[TranscriptSegment]
    total_segments: int