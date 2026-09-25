from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Playlist(Base):
    __tablename__ = "playlists"

    playlist_id: Mapped[str] = mapped_column(String(255), primary_key=True, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled playlist")
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(String, nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    videos: Mapped[list["Video"]] = relationship(back_populates="playlist", cascade="all, delete-orphan")
