"""Validated HTTP request models."""

from pydantic import BaseModel, Field


class UrlPayload(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class PlaylistCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class PlaybackUpdate(BaseModel):
    mode: str | None = None
    quality: str | None = None
    audio_quality: str | None = None
    history_limit: int | None = Field(default=None, ge=0, le=100000)


class PlaylistUpdate(PlaybackUpdate):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class DeleteRequest(BaseModel):
    delete_videos: bool = False


class PlaylistVideoRequest(BaseModel):
    video_id: int | None = None
    url: str | None = Field(default=None, max_length=2048)


class PlaylistMoveRequest(BaseModel):
    target_video_id: int
    after: bool = False


class RetentionRequest(BaseModel):
    retained: bool


class HistoryRequest(BaseModel):
    position: float = Field(ge=0)
    duration: float | None = Field(default=None, ge=0)


class CatalogRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CatalogChannelsRequest(BaseModel):
    channel_ids: list[int] = Field(max_length=100000)


class MoveRequest(BaseModel):
    direction: str


class PersonalSettingsRequest(BaseModel):
    default_mode: str
    default_quality: str
    default_audio_quality: str
    history_limit: int = Field(ge=0, le=100000)


class InstanceSettingsRequest(BaseModel):
    batch_size: int = Field(ge=1, le=50)
    lot_wait_seconds: int
    campaign_duration_seconds: int
    temporary_retention_days: int = Field(ge=1, le=365)
    metadata_language: str | None = None
