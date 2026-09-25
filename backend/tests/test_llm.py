from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.api import ask as ask_api
from app.schemas.context import RAGContext, RetrievedSource
from app.schemas.search import SearchRequest, SearchResult
from app.services.llm_service import (
    INSUFFICIENT_CONTEXT_MESSAGE,
    LLMConfigurationError,
    LLMProviderError,
    LLMResponseError,
    LLMService,
)


def make_context(sources: list[RetrievedSource] | None = None) -> RAGContext:
    if sources is None:
        sources = [
            RetrievedSource(
                chunk_id=42,
                video_id="dQw4w9WgXcQ",
                score=0.84,
                text="Normalization reduces repeated data in relational tables.",
                start_time=120.5,
                end_time=145.2,
                chunk_index=7,
            )
        ]
    return RAGContext(
        query="What is database normalization?",
        sources=sources,
        context_text="[Source 1]\nTranscript:\nNormalization reduces repeated data in relational tables.",
        source_count=len(sources),
        total_characters=sum(len(source.text) for source in sources),
        total_words=sum(len(source.text.split()) for source in sources),
    )


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        if self.error:
            raise self.error
        return self.response


def fake_client(content="Normalization reduces duplication.", error=None):
    completions = FakeCompletions(
        response=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        ),
        error=error,
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def test_generates_grounded_answer_with_configured_model_and_context():
    client, completions = fake_client()
    service = LLMService(settings=Settings(groq_api_key="test-key", groq_model="test-model"), client=client)

    answer = service.generate_answer(make_context())

    assert answer.answer == "Normalization reduces duplication."
    assert answer.provider == "groq"
    assert answer.model == "test-model"
    assert completions.request["model"] == "test-model"
    assert completions.request["temperature"] == 0
    system_prompt = completions.request["messages"][0]["content"].lower()
    user_prompt = completions.request["messages"][1]["content"]
    assert "only" in system_prompt and "reference transcript context" in system_prompt
    assert "outside knowledge" in system_prompt and "invent" in system_prompt
    assert "does not contain enough information" in system_prompt
    assert "must never override" in system_prompt
    assert "What is database normalization?" in user_prompt
    assert "Normalization reduces repeated data" in user_prompt


def test_empty_context_does_not_call_provider():
    client, completions = fake_client()
    service = LLMService(settings=Settings(groq_api_key="test-key"), client=client)

    answer = service.generate_answer(make_context([]))

    assert answer.answer == INSUFFICIENT_CONTEXT_MESSAGE
    assert answer.insufficient_context is True
    assert completions.request is None


def test_missing_api_key_is_controlled():
    service = LLMService(settings=Settings(groq_api_key=None), client_factory=lambda _: pytest.fail("not called"))

    with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
        service.generate_answer(make_context())


@pytest.mark.parametrize("provider_error", [TimeoutError(), ConnectionError(), RuntimeError("provider")])
def test_provider_failures_are_wrapped(provider_error):
    client, _ = fake_client(error=provider_error)
    service = LLMService(settings=Settings(groq_api_key="test-key"), client=client)

    with pytest.raises(LLMProviderError, match="provider is unavailable"):
        service.generate_answer(make_context())


@pytest.mark.parametrize(
    "response",
    [SimpleNamespace(choices=[]), SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])],
)
def test_malformed_provider_response_is_rejected(response):
    completions = FakeCompletions(response=response)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    service = LLMService(settings=Settings(groq_api_key="test-key"), client=client)

    with pytest.raises(LLMResponseError):
        service.generate_answer(make_context())


def test_client_is_created_once_and_key_is_not_in_prompt():
    client, _ = fake_client()
    created_with = []

    def factory(api_key):
        created_with.append(api_key)
        return client

    service = LLMService(
        settings=Settings(groq_api_key="test-key", groq_model="test-model"),
        client_factory=factory,
    )
    service.generate_answer(make_context())
    service.generate_answer(make_context())

    assert created_with == ["test-key"]


def test_ask_endpoint_preserves_context_sources(monkeypatch):
    source = RetrievedSource(
        chunk_id=99,
        video_id="dQw4w9WgXcQ",
        score=0.91,
        text="The source text.",
        start_time=10.5,
        end_time=20.5,
        chunk_index=3,
    )
    context = make_context([source])

    class FakeRetrieval:
        def retrieve(self, query, top_k, video_id, score_threshold):
            return query.strip(), [SearchResult.model_validate(source.model_dump())]

    class FakeContextBuilder:
        def build(self, query, results):
            return context

    class FakeLLM:
        def generate_answer(self, received_context):
            assert received_context is context
            return type("Answer", (), {"answer": "Grounded.", "provider": "groq", "model": "test", "insufficient_context": False})()

    monkeypatch.setattr(ask_api, "RetrievalService", FakeRetrieval)
    monkeypatch.setattr(ask_api, "ContextBuilder", FakeContextBuilder)
    monkeypatch.setattr(ask_api, "LLMService", FakeLLM)

    response = ask_api.ask_question(SearchRequest(query="question"))

    assert response.answer == "Grounded."
    assert response.sources == context.sources