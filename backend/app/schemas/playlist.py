from datetime import datetime

from pydantic import BaseModel, HttpUrl


class PlaylistMetadata(BaseModel):
    playlist_id: str
    title: str
    description: str
    thumbnail: HttpUrl | None = None
    channel_id: str | None = None
    channel_title: str | None = None
    published_at: datetime | None = None


class PlaylistVideo(BaseModel):
    video_id: str
    title: str
    description: str
    thumbnail: HttpUrl | None = None
    position: int
    published_at: datetime | None = None
    video_url: HttpUrl
    duration: str | None = None
    available: bool = True


class PlaylistResponse(BaseModel):
    playlist: PlaylistMetadata
    videos: list[PlaylistVideo]
    total_videos: int = 0