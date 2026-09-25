from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    playlist_id: Mapped[str] = mapped_column(ForeignKey("playlists.playlist_id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled video")
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    video_url: Mapped[str] = mapped_column(String, nullable=False)
    duration: Mapped[str | None] = mapped_column(String(64), nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    playlist: Mapped["Playlist"] = relationship(back_populates="videos")

    __table_args__ = (
        Index("ix_videos_playlist_id_video_id", "playlist_id", "video_id", unique=True),
        Index("ix_videos_playlist_id_position", "playlist_id", "position"),
    )
