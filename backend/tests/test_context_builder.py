import math

import pytest

from app.core.config import Settings
from app.schemas.search import SearchResult
from app.services.context_builder import ContextBuilder, ContextBuilderInputError


VIDEO_A = "dQw4w9WgXcQ"
VIDEO_B = "jNQXAC9IVRw"


def result(chunk_id: int, video_id: str = VIDEO_A, score: float = 0.8, text: str | None = None, start: float | None = None):
    return SearchResult(
        chunk_id=chunk_id,
        video_id=video_id,
        score=score,
        text=text or f"Transcript for chunk {chunk_id}.",
        start_time=float(chunk_id if start is None else start),
        end_time=float((chunk_id if start is None else start) + 10),
        chunk_index=chunk_id,
        language_code="en",
        segment_start_index=chunk_id,
        segment_end_index=chunk_id + 1,
        character_count=len(text or f"Transcript for chunk {chunk_id}."),
        word_count=len((text or f"Transcript for chunk {chunk_id}.").split()),
    )


def test_builds_context_and_preserves_metadata():
    context = ContextBuilder().build("  What is this? ", [result(4, score=0.91)])

    assert context.query == "What is this?"
    assert context.sources[0].model_dump(exclude_none=True) == result(4, score=0.91).model_dump(exclude_none=True)
    assert "[Source 1]" in context.context_text
    assert "Timestamp: 00:04 - 00:14" in context.context_text


def test_groups_same_video_chronologically_but_keeps_video_relevance_order():
    context = ContextBuilder().build(
        "question",
        [result(5, score=0.95), result(2, score=0.7), result(4, score=0.8), result(8, VIDEO_B, 0.9)],
    )

    assert [(source.video_id, source.chunk_id) for source in context.sources] == [
        (VIDEO_A, 2),
        (VIDEO_A, 4),
        (VIDEO_A, 5),
        (VIDEO_B, 8),
    ]


def test_removes_duplicate_keys_and_keeps_highest_score():
    context = ContextBuilder().build("question", [result(1, score=0.4), result(1, score=0.9), result(2)])

    assert [source.chunk_id for source in context.sources] == [1, 2]
    assert context.sources[0].score == 0.9


def test_removes_exact_duplicate_text_within_video():
    context = ContextBuilder().build("question", [result(1, text="same"), result(2, text="same")])

    assert [source.chunk_id for source in context.sources] == [1]


def test_keeps_repeated_text_when_chunks_are_not_adjacent():
    context = ContextBuilder().build("question", [result(1, text="same"), result(3, text="same", start=30)])

    assert [source.chunk_id for source in context.sources] == [1, 3]


def test_context_limit_excludes_complete_lower_priority_sources():
    settings = Settings(rag_max_context_chars=220, rag_max_sources=5)
    context = ContextBuilder(settings).build("question", [result(1, score=0.9, text="a" * 20), result(2, text="b" * 200)])

    assert len(context.sources) == 1
    assert len(context.context_text) <= 220
    assert context.sources[0].text == "a" * 20


def test_max_sources_and_empty_results():
    settings = Settings(rag_max_sources=2)
    context = ContextBuilder(settings).build("question", [result(index) for index in range(5)])
    empty = ContextBuilder(settings).build("question", [])

    assert len(context.sources) == 2
    assert empty.sources == []
    assert empty.context_text == ""


@pytest.mark.parametrize(
    "bad_result",
    [
        result(1, text=" "),
        result(1, score=math.nan),
        result(1, score=math.inf),
        {"chunk_id": 1},
    ],
)
def test_invalid_results_are_rejected(bad_result):
    with pytest.raises(ContextBuilderInputError):
        ContextBuilder().build("question", [bad_result])


def test_invalid_query_and_timestamps_are_rejected():
    invalid_time = result(1).model_copy(update={"end_time": -1.0})
    missing_video = result(1).model_construct(video_id="", _fields_set={"chunk_id", "video_id"})
    malformed_score = result(1).model_construct(score="invalid", _fields_set={"chunk_id", "score"})

    with pytest.raises(ContextBuilderInputError):
        ContextBuilder().build(" ", [])
    with pytest.raises(ContextBuilderInputError):
        ContextBuilder().build("question", [invalid_time])
    with pytest.raises(ContextBuilderInputError):
        ContextBuilder().build("question", [missing_video])
    with pytest.raises(ContextBuilderInputError):
        ContextBuilder().build("question", [malformed_score])


def test_build_is_deterministic():
    results = [result(3, score=0.7), result(1, score=0.9), result(2, score=0.8)]

    first = ContextBuilder().build("question", results)
    second = ContextBuilder().build("question", results)

    assert first.model_dump() == second.model_dump()