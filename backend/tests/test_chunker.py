from app.services.transcript.chunker import ChunkingConfig, TranscriptChunker


def segments(*items: tuple[str, float, float]) -> list[dict]:
    return [{"text": text, "start": start, "duration": duration} for text, start, duration in items]


def test_empty_transcript_returns_no_chunks() -> None:
    assert TranscriptChunker().chunk("video", "en", []) == []


def test_single_segment_preserves_text_and_timestamps() -> None:
    result = TranscriptChunker().chunk("video", "en", segments((" Hello   world ", 12.5, 2.25)))

    assert result == [{
        "video_id": "video",
        "language_code": "en",
        "chunk_index": 0,
        "text": "Hello world",
        "start_time": 12.5,
        "end_time": 14.75,
        "segment_start_index": 0,
        "segment_end_index": 0,
        "character_count": 11,
        "word_count": 2,
    }]


def test_chunk_size_and_overlap_use_complete_segments() -> None:
    config = ChunkingConfig(target_words=5, overlap_words=2)
    transcript = segments(
        ("one two", 0, 1),
        ("three four", 1, 1),
        ("five six", 2, 1),
        ("seven eight", 3, 1),
    )

    result = TranscriptChunker(config).chunk("video", "en", transcript)

    assert [chunk["text"] for chunk in result] == [
        "one two three four",
        "three four five six",
        "five six seven eight",
    ]
    assert [(chunk["segment_start_index"], chunk["segment_end_index"]) for chunk in result] == [
        (0, 1),
        (1, 2),
        (2, 3),
    ]


def test_large_segment_is_not_split_or_discarded() -> None:
    result = TranscriptChunker(ChunkingConfig(target_words=2, overlap_words=1)).chunk(
        "video", "en", segments(("one two three four", 3.25, 0.0), ("five", 3.25, 1.5))
    )

    assert [chunk["text"] for chunk in result] == ["one two three four", "five"]
    assert result[0]["end_time"] == 3.25


def test_fractional_timestamps_and_gaps_use_actual_segment_times() -> None:
    result = TranscriptChunker(ChunkingConfig(target_words=10, overlap_words=0)).chunk(
        "video", "en", segments(("first", 1.125, 0.375), ("second", 8.5, 0.625))
    )

    assert result[0]["start_time"] == 1.125
    assert result[0]["end_time"] == 9.125


def test_all_content_is_represented_even_with_short_chunks() -> None:
    transcript = segments(("alpha", 0, 0), ("beta", 1, 0), ("gamma", 2, 0))
    result = TranscriptChunker(ChunkingConfig(target_words=1, overlap_words=0)).chunk("video", "en", transcript)

    assert "alpha" in " ".join(chunk["text"] for chunk in result)
    assert "beta" in " ".join(chunk["text"] for chunk in result)
    assert "gamma" in " ".join(chunk["text"] for chunk in result)


def test_long_transcript_preserves_input_segment_order() -> None:
    transcript = segments(*[(f"word-{index}", float(index), 0.5) for index in range(25)])
    result = TranscriptChunker(ChunkingConfig(target_words=5, overlap_words=1)).chunk("video", "en", transcript)
    combined = " ".join(chunk["text"] for chunk in result)

    assert [chunk["chunk_index"] for chunk in result] == list(range(len(result)))
    assert [combined.index(f"word-{index}") for index in range(25)] == sorted(
        combined.index(f"word-{index}") for index in range(25)
    )
    assert all(f"word-{index}" in combined for index in range(25))