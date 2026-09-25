from pydantic import BaseModel, ConfigDict, StrictStr

from app.schemas.context import RetrievedSource


class LLMAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: StrictStr
    provider: str | None = None
    model: str | None = None
    insufficient_context: bool = False


class AskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    answer: str
    sources: list[RetrievedSource]
    provider: str | None = None
    model: str | None = None
    insufficient_context: bool = False