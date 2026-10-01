from __future__ import annotations

import logging
import time
from threading import Lock
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.repositories.playlist_repository import PlaylistRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantConfigurationError, QdrantService
from app.services.transcript.chunk_service import TranscriptChunkService
from app.services.transcript.transcript_service import (
    TranscriptNotAvailableError,
    TranscriptProviderError,
    TranscriptService,
    VideoUnavailableError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaylistIndexReport:
    status: str
    total_videos: int
    processed_videos: int
    indexed_videos: int
    skipped_videos: int
    failed_videos: int
    last_error: str | None = None
    video_diagnostics: list[dict[str, str]] | None = None
    transcript_access_blocked: bool = False


class PlaylistIndexingService:
    _max_active_jobs = 4
    _jobs_lock = Lock()
    _active_playlists: set[str] = set()

    def __init__(
        self,
        settings: Settings,
        playlist_repository: PlaylistRepository,
        transcript_repository: TranscriptRepository | None = None,
        transcript_service: TranscriptService | None = None,
        chunk_service: TranscriptChunkService | None = None,
        embedding_service: EmbeddingService | None = None,
        qdrant_service: QdrantService | None = None,
    ) -> None:
        self.settings = settings
        self.playlist_repository = playlist_repository
        transcript_repository = transcript_repository or TranscriptRepository()
        self.transcript_service = transcript_service or TranscriptService(transcript_repository=transcript_repository)
        self.chunk_service = chunk_service or TranscriptChunkService(transcript_repository=transcript_repository)
        self.embedding_service = embedding_service or EmbeddingService()
        self.qdrant_service = qdrant_service

    def prepare_indexing(self, playlist_id: str) -> PlaylistIndexReport:
        videos = self.playlist_repository.get_playlist_videos(playlist_id)
        total_videos = len([video for video in videos if video.available])
        existing = self.playlist_repository.get_index_status(playlist_id)
        if existing is not None and existing.status in {
            "INDEXING",
            "INDEXING_COMPLETED",
            "INDEXING_PARTIAL",
            "indexing",
            "ready",
            "partially_indexed",
        }:
            return self._report(existing)

        self.playlist_repository.save_index_status(
            playlist_id,
            {
                "status": "PENDING",
                "total_videos": total_videos,
                "processed_videos": 0,
                "indexed_videos": 0,
                "skipped_videos": 0,
                "failed_videos": 0,
                "last_error": None,
                "video_diagnostics": [],
            },
        )
        return PlaylistIndexReport("PENDING", total_videos, 0, 0, 0, 0, None)

    def schedule_indexing(self, playlist_id: str) -> bool:
        with self._jobs_lock:
            if playlist_id in self._active_playlists:
                return False
            if len(self._active_playlists) >= self._max_active_jobs:
                return False
            self._active_playlists.add(playlist_id)
        return True

    def run_indexing(self, playlist_id: str) -> PlaylistIndexReport:
        try:
            return self.index_playlist(playlist_id)
        finally:
            with self._jobs_lock:
                self._active_playlists.discard(playlist_id)

    def index_playlist(self, playlist_id: str) -> PlaylistIndexReport:
        videos = self.playlist_repository.get_playlist_videos(playlist_id)
        total_videos = len([video for video in videos if video.available])
        existing = self.playlist_repository.get_index_status(playlist_id)
        if existing is not None and existing.status in {"INDEXING_COMPLETED", "ready"} and existing.total_videos == total_videos:
            return self._report(existing)

        self.playlist_repository.save_index_status(
            playlist_id,
            {
                "status": "INDEXING",
                "total_videos": total_videos,
                "processed_videos": 0,
                "indexed_videos": 0,
                "skipped_videos": 0,
                "failed_videos": 0,
                "last_error": None,
            },
        )
        processed = 0
        indexed = 0
        skipped = 0
        failed = 0
        errors: list[str] = []
        diagnostics: list[dict[str, str]] = []
        transcript_access_blocked = False

        for video in videos:
            if not video.available:
                skipped += 1
                continue
            stage = "transcript"
            try:
                transcript = self.transcript_service.get_transcript(video.video_id)
                stage = "chunks"
                self.chunk_service.get_chunks(
                    video.video_id,
                    transcript.language,
                    playlist_id=playlist_id,
                )
                chunks = self._stored_chunks(video.video_id, transcript.language, playlist_id)
                if not chunks:
                    raise RuntimeError("Transcript produced no chunks.")

                stage = "embedding"
                pending = [
                    chunk
                    for chunk in chunks
                    if chunk.embedding is None or chunk.embedding_model != self.embedding_service.model_name
                ]
                generated = self.embedding_service.embed_chunks(pending)
                if generated:
                    dimension = len(generated[0].vector)
                    self._transcript_repository.save_embeddings(
                        {item.chunk_id: item.vector for item in generated},
                        self.embedding_service.model_name,
                        dimension,
                    )
                    chunks = self._stored_chunks(video.video_id, transcript.language, playlist_id)

                embeddings = {
                    chunk.id: self.embedding_service.decode_vector(chunk.embedding)
                    for chunk in chunks
                    if chunk.embedding is not None
                }
                embeddings = {chunk_id: vector for chunk_id, vector in embeddings.items() if vector is not None}
                if len(embeddings) != len(chunks):
                    raise RuntimeError(
                        f"Embedding set is incomplete: {len(embeddings)} of {len(chunks)} chunks have vectors."
                    )

                stage = "qdrant"
                qdrant_service = self.qdrant_service or QdrantService(self.settings)
                sync = qdrant_service.sync_chunks(chunks, embeddings)
                if sync.get("upserted", 0) != len(chunks):
                    raise QdrantConfigurationError(
                        f"Only {sync.get('upserted', 0)} of {len(chunks)} chunks reached Qdrant."
                    )
                indexed += 1
                logger.info(
                    "Indexed playlist video",
                    extra={"playlist_id": playlist_id, "video_id": video.video_id, "status": "indexed", "chunks": len(chunks)},
                )
            except TranscriptNotAvailableError as error:
                skipped += 1
                diagnostic = self._diagnostic(video, "no_transcript", "transcript", error)
                diagnostics.append(diagnostic)
                errors.append(self._format_diagnostic(diagnostic))
                logger.warning("Playlist video skipped: playlist_id=%s video_id=%s reason=%s", playlist_id, video.video_id, error)
            except Exception as error:
                failed += 1
                if self._is_transcript_access_blocked(error):
                    transcript_access_blocked = True
                diagnostic = self._diagnostic(video, "failed", stage, error)
                diagnostics.append(diagnostic)
                errors.append(self._format_diagnostic(diagnostic))
                logger.exception(
                    "Playlist video indexing failed: playlist_id=%s video_id=%s title=%s stage=%s",
                    playlist_id,
                    video.video_id,
                    video.title,
                    stage,
                )
            finally:
                if video.available:
                    processed += 1
                    self._save_progress(
                        playlist_id, total_videos, processed, indexed, skipped, failed, errors, diagnostics, transcript_access_blocked
                    )
                    if self.settings.transcript_request_delay_seconds > 0:
                        time.sleep(self.settings.transcript_request_delay_seconds)

        status = (
            "INDEXING_COMPLETED"
            if total_videos > 0 and indexed == total_videos
            else "INDEXING_PARTIAL"
            if indexed
            else "INDEXING_FAILED"
        )
        report = PlaylistIndexReport(
            status,
            total_videos,
            processed,
            indexed,
            skipped,
            failed,
            "; ".join(errors)[:4000] or None,
            diagnostics,
            transcript_access_blocked,
        )
        self.playlist_repository.save_index_status(playlist_id, report.__dict__)
        return report

    def _save_progress(
        self,
        playlist_id: str,
        total_videos: int,
        processed: int,
        indexed: int,
        skipped: int,
        failed: int,
        errors: list[str],
        diagnostics: list[dict[str, str]],
        transcript_access_blocked: bool = False,
    ) -> None:
        self.playlist_repository.save_index_status(
            playlist_id,
            {
                "status": "INDEXING",
                "total_videos": total_videos,
                "processed_videos": processed,
                "indexed_videos": indexed,
                "skipped_videos": skipped,
                "failed_videos": failed,
                "last_error": "; ".join(errors)[:4000] or None,
                "video_diagnostics": diagnostics,
                "transcript_access_blocked": transcript_access_blocked,
            },
        )

    @staticmethod
    def _is_transcript_access_blocked(error: Exception) -> bool:
        """Return True when the error conclusively indicates YouTube is blocking
        transcript requests from this network/IP (auth block or rate-limit)."""
        from app.services.transcript.transcript_service import TranscriptProviderError
        if isinstance(error, TranscriptProviderError):
            return error.error_code in {"PROVIDER_AUTH_ERROR", "PROVIDER_RATE_LIMIT"}
        # Fallback: catch common library error class names for IP/request blocking
        error_name = type(error).__name__
        return error_name in {"IpBlocked", "RequestBlocked"} or "blocked" in error_name.lower()


    @property
    def _transcript_repository(self) -> TranscriptRepository:
        return self.chunk_service.transcript_repository

    def _stored_chunks(self, video_id: str, language: str | None, playlist_id: str) -> list[Any]:
        return self._transcript_repository.get_chunks(video_id, language, playlist_id)

    @staticmethod
    def _root_exception(error: Exception) -> Exception:
        root = error
        while root.__cause__ is not None:
            root = root.__cause__
        return root

    @classmethod
    def _diagnostic(cls, video: Any, status: str, stage: str, error: Exception) -> dict[str, str]:
        root = error if isinstance(error, TranscriptProviderError) else cls._root_exception(error)
        if isinstance(error, TranscriptProviderError) and error.error_code == "PROVIDER_AUTH_ERROR":
            message = "Transcript unavailable — YouTube blocked transcript access."
        elif isinstance(error, TranscriptProviderError) and error.error_code == "PROVIDER_RATE_LIMIT":
            message = "Transcript unavailable — YouTube rate-limited transcript access."
        else:
            message = str(root).strip() or str(error).strip() or type(error).__name__
        return {
            "video_id": str(video.video_id),
            "title": str(video.title),
            "status": status,
            "error": message[:240],
            "technical_details": f"{type(root).__name__}: {str(root).strip()}"[:2000],
            "stage": stage,
        }

    @staticmethod
    def _format_diagnostic(diagnostic: dict[str, str]) -> str:
        return f"{diagnostic['video_id']} [{diagnostic['stage']}]: {diagnostic['error']}"

    @staticmethod
    def _report(status: Any) -> PlaylistIndexReport:
        normalized_status = {
            "pending": "PENDING",
            "indexing": "INDEXING",
            "ready": "INDEXING_COMPLETED",
            "partially_indexed": "INDEXING_PARTIAL",
            "failed": "INDEXING_FAILED",
        }.get(status.status, status.status)
        return PlaylistIndexReport(
            normalized_status,
            status.total_videos,
            status.processed_videos,
            status.indexed_videos,
            status.skipped_videos,
            status.failed_videos,
            status.last_error,
            getattr(status, "video_diagnostics", None) or [],
            getattr(status, "transcript_access_blocked", False),
        )