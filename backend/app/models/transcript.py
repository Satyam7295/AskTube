from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String(11), nullable=False, index=True)
    language_code: Mapped[str] = mapped_column(String(16), nullable=False)
    language_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_generated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    segments: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("video_id", "language_code", name="uq_transcripts_video_language"),)