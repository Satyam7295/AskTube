from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi import BackgroundTasks

from app.core.config import Settings
from app.api import playlists as playlists_api
from app.schemas.playlist import PlaylistMetadata, PlaylistResponse, PlaylistVideo
from app.services.playlist_indexing_service import PlaylistIndexingService
from app.services.playlist_service import PlaylistService


PLAYLIST_ID = "PL_TEST_INDEX"


def video(video_id: str, position: int = 0):
    return SimpleNamespace(video_id=video_id, position=position, available=True, title=f"Video {video_id}")


class FakePlaylistRepository:
    def __init__(self, videos):
        self.videos = videos
        self.status = None

    def get_playlist_videos(self, playlist_id):
        return self.videos

    def get_index_status(self, playlist_id):
        return self.status

    def save_index_status(self, playlist_id, values):
        self.status = SimpleNamespace(playlist_id=playlist_id, **values)
        return self.status


class FakeTranscriptRepository:
    def __init__(self, chunks_by_video):
        self.chunks_by_video = chunks_by_video
        self.save_calls = 0

    def get_chunks(self, video_id, language_code=None, playlist_id=None):
        return self.chunks_by_video.get(video_id, [])

    def save_embeddings(self, embeddings, model_name, dimension):
        self.save_calls += 1
        for chunks in self.chunks_by_video.values():
            for chunk in chunks:
                if chunk.id in embeddings:
                    chunk.embedding = str(embeddings[chunk.id])
                    chunk.embedding_model = model_name
                    chunk.embedding_dimension = dimension


class FakeTranscriptService:
    def __init__(self, unavailable=()):
        self.unavailable = set(unavailable)
        self.calls = []

    def get_transcript(self, video_id):
        self.calls.append(video_id)
        if video_id in self.unavailable:
            from app.services.transcript.transcript_service import TranscriptNotAvailableError

            raise TranscriptNotAvailableError("no captions")
        return SimpleNamespace(language="en")


class FakeChunkService:
    def __init__(self, repository):
        self.transcript_repository = repository

    def get_chunks(self, video_id, language=None, playlist_id=None):
        return SimpleNamespace(chunks=self.transcript_repository.get_chunks(video_id, language, playlist_id))


class FakeEmbeddingService:
    model_name = "test-model"

    def __init__(self):
        self.calls = 0

    def embed_chunks(self, chunks):
        self.calls += 1
        for chunk in chunks:
            chunk.embedding = "[1.0, 0.0]"
            chunk.embedding_model = self.model_name
            chunk.embedding_dimension = 2
        return [SimpleNamespace(chunk_id=chunk.id, vector=[1.0, 0.0]) for chunk in chunks]

    @staticmethod
    def decode_vector(value):
        return [1.0, 0.0] if value else None


class FakeQdrantService:
    def __init__(self):
        self.points = []

    def sync_chunks(self, chunks, embeddings):
        self.points.extend(
            {
                "playlist_id": chunk.playlist_id,
                "video_id": chunk.video_id,
                "chunk_id": chunk.id,
            }
            for chunk in chunks
            if chunk.id in embeddings
        )
        return {"upserted": len(chunks), "total_chunks": len(chunks)}


def make_chunk(chunk_id, video_id):
    return SimpleNamespace(
        id=chunk_id,
        video_id=video_id,
        playlist_id=PLAYLIST_ID,
        embedding=None,
        embedding_model=None,
        text="A useful transcript passage",
        chunk_index=0,
    )


def make_indexer(videos, unavailable=()):
    repository = FakePlaylistRepository(videos)
    transcript_repository = FakeTranscriptRepository(
        {item.video_id: [make_chunk(index + 1, item.video_id)] for index, item in enumerate(videos)}
    )
    embedding = FakeEmbeddingService()
    qdrant = FakeQdrantService()
    indexer = PlaylistIndexingService(
        Settings(qdrant_url="http://test", embedding_dimension=2),
        repository,
        transcript_repository=transcript_repository,
        transcript_service=FakeTranscriptService(unavailable),
        chunk_service=FakeChunkService(transcript_repository),
        embedding_service=embedding,
        qdrant_service=qdrant,
    )
    return indexer, repository, transcript_repository, embedding, qdrant


def test_playlist_ingestion_invokes_indexing_service():
    repository = FakePlaylistRepository([])
    indexer = SimpleNamespace(
        prepare_indexing=lambda playlist_id: SimpleNamespace(
            status="pending", processed_videos=0, indexed_videos=0, skipped_videos=0, failed_videos=0
        )
    )
    youtube = SimpleNamespace(
        get_playlist=AsyncMock(
            return_value=PlaylistResponse(
                playlist=PlaylistMetadata(playlist_id=PLAYLIST_ID, title="Test", description=""),
                videos=[],
            )
        )
    )
    service = PlaylistService(Settings(), repository=repository, indexing_service=indexer)
    service.youtube_service = youtube
    repository.upsert_playlist_with_videos = lambda *_args: None

    import asyncio

    response = asyncio.run(service.get_playlist(PLAYLIST_ID))
    assert response.indexing_status == "pending"
    assert response.indexed_videos == 0


def test_multiple_videos_are_indexed_and_payloads_keep_playlist_and_video():
    indexer, repository, _, embedding, qdrant = make_indexer([video("video_one1", 0), video("video_two2", 1)])
    report = indexer.index_playlist(PLAYLIST_ID)

    assert report.status == "ready"
    assert report.indexed_videos == 2
    assert {point["video_id"] for point in qdrant.points} == {"video_one1", "video_two2"}
    assert all(point["playlist_id"] == PLAYLIST_ID for point in qdrant.points)
    assert repository.status.status == "ready"
    assert embedding.calls == 2


def test_missing_transcript_does_not_abort_other_videos_and_reports_partial():
    indexer, repository, _, _, qdrant = make_indexer(
        [video("video_one1", 0), video("video_two2", 1)], unavailable=("video_one1",)
    )
    report = indexer.index_playlist(PLAYLIST_ID)

    assert report.status == "partially_indexed"
    assert report.skipped_videos == 1
    assert report.indexed_videos == 1
    assert [point["video_id"] for point in qdrant.points] == ["video_two2"]
    assert repository.status.last_error


def test_cached_embeddings_are_reused_and_ready_reingestion_is_idempotent():
    indexer, _, transcript_repository, embedding, qdrant = make_indexer([video("video_one1")])
    first = indexer.index_playlist(PLAYLIST_ID)
    second = indexer.index_playlist(PLAYLIST_ID)

    assert first.status == second.status == "ready"
    assert embedding.calls == 1
    assert transcript_repository.save_calls == 1
    assert len(qdrant.points) == 1


def test_provider_failure_does_not_report_ready():
    indexer, repository, _, _, _ = make_indexer([video("video_one1")], unavailable=("video_one1",))
    report = indexer.index_playlist(PLAYLIST_ID)

    assert report.status == "failed"
    assert repository.status.status == "failed"


def test_duplicate_background_jobs_are_prevented():
    indexer, _, _, _, _ = make_indexer([video("video_one1")])

    assert indexer.schedule_indexing(PLAYLIST_ID) is True
    assert indexer.schedule_indexing(PLAYLIST_ID) is False
    indexer.run_indexing(PLAYLIST_ID)
    assert indexer.schedule_indexing(PLAYLIST_ID) is True
    indexer.run_indexing(PLAYLIST_ID)


def test_progress_transitions_from_indexing_to_ready():
    indexer, repository, _, _, _ = make_indexer([video("video_one1"), video("video_two2")])

    report = indexer.index_playlist(PLAYLIST_ID)

    assert report.status == "ready"
    assert report.processed_videos == 2
    assert repository.status.processed_videos == 2
    assert repository.status.indexed_videos == 2

def test_playlist_persistence_schedules_background_work_without_running_it_inline():
    repository = FakePlaylistRepository([])
    started = []
    indexer = SimpleNamespace(
        prepare_indexing=lambda playlist_id: SimpleNamespace(
            status="pending", processed_videos=0, indexed_videos=0, skipped_videos=0, failed_videos=0
        ),
        schedule_indexing=lambda playlist_id: True,
        run_indexing=lambda playlist_id: started.append(playlist_id),
    )
    service = PlaylistService(Settings(), repository=repository, indexing_service=indexer)
    tasks = BackgroundTasks()

    response = service.indexing_service.prepare_indexing(PLAYLIST_ID)
    service.schedule_indexing(PLAYLIST_ID, tasks)

    assert response.status == "pending"
    assert started == []
    assert len(tasks.tasks) == 1
    tasks.tasks[0].func(*tasks.tasks[0].args, **tasks.tasks[0].kwargs)
    assert started == [PLAYLIST_ID]


def test_playlist_route_returns_pending_and_queues_background_job(monkeypatch):
    response = PlaylistResponse(
        playlist=PlaylistMetadata(playlist_id=PLAYLIST_ID, title="Test", description=""),
        videos=[],
        indexing_status="pending",
    )
    scheduled = []

    class FakeService:
        async def get_playlist(self, playlist_id):
            return response

        def schedule_indexing(self, playlist_id, background_tasks):
            scheduled.append((playlist_id, background_tasks))

    monkeypatch.setattr(playlists_api, "PlaylistService", lambda settings: FakeService())

    import asyncio

    tasks = BackgroundTasks()
    returned = asyncio.run(playlists_api.get_playlist(PLAYLIST_ID, tasks))

    assert returned.indexing_status == "pending"
    assert scheduled == [(PLAYLIST_ID, tasks)]