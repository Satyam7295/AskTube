from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlaylistIndexStatus(Base):
    __tablename__ = "playlist_index_status"

    playlist_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    total_videos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_videos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    indexed_videos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_videos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_videos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transcript_access_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_diagnostics: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )