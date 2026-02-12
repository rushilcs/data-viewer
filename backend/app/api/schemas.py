"""Pydantic schemas per docs/04-api-spec.md."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def _config_forbid(**kwargs):
    return ConfigDict(extra="forbid", **kwargs)


# ----- Auth -----
class LoginRequest(BaseModel):
    model_config = _config_forbid()
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    model_config = _config_forbid()
    email: EmailStr
    password: str


class UserProfile(BaseModel):
    model_config = _config_forbid()
    id: UUID
    email: str
    org_id: UUID
    org_name: str
    role: str


# ----- Datasets -----
class DatasetSummary(BaseModel):
    model_config = _config_forbid()
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    published_at: datetime | None
    tags: list[str] | None


class DatasetDetail(BaseModel):
    model_config = _config_forbid()
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    published_at: datetime | None
    tags: list[str] | None
    created_by_user_id: UUID


# ----- Items -----
class AssetMetadata(BaseModel):
    model_config = _config_forbid()
    id: UUID
    kind: str
    content_type: str
    byte_size: int


class AnnotationOut(BaseModel):
    model_config = _config_forbid(populate_by_name=True)
    schema_: str = Field(alias="schema")
    data: dict


class ItemSummary(BaseModel):
    model_config = _config_forbid()
    id: UUID
    type: str
    title: str | None
    summary: str | None
    created_at: datetime


class TimelineEventNormalized(BaseModel):
    model_config = _config_forbid()
    t_start: float
    t_end: float | None = None
    label: str | None = None
    metadata: dict | None = None
    track: str | None = None


class CaptionSegmentNormalized(BaseModel):
    model_config = _config_forbid()
    t_start: float
    t_end: float | None = None
    text: str | None = None


class ItemDetail(BaseModel):
    model_config = _config_forbid()
    item: dict  # { id, type, title, summary, payload, created_at }
    assets: list[AssetMetadata]
    annotations: list[AnnotationOut]
    timeline_events: list[TimelineEventNormalized] | None = None  # for video_with_timeline
    caption_segments: list[CaptionSegmentNormalized] | None = None  # for audio_with_captions


# ----- Pagination -----
class PaginatedItems(BaseModel):
    model_config = _config_forbid()
    items: list[ItemSummary]
    next_cursor: str | None
    has_more: bool


class ItemTypeCounts(BaseModel):
    model_config = _config_forbid()
    counts: dict[str, int]
    total: int


# ----- Assets -----
class SignedUrlResponse(BaseModel):
    model_config = _config_forbid()
    url: str
    expires_at: datetime


# ----- Ingest -----
class IngestCreateDatasetRequest(BaseModel):
    model_config = _config_forbid()
    name: str
    description: str | None = None
    tags: list[str] | None = None


class IngestCreateDatasetResponse(BaseModel):
    model_config = _config_forbid()
    dataset_id: UUID
    status: str = "draft"


class IngestFileSpec(BaseModel):
    model_config = _config_forbid()
    filename: str
    kind: str  # image | video | audio | other
    content_type: str
    byte_size: int


class IngestAssetsBatchRequest(BaseModel):
    model_config = _config_forbid()
    dataset_id: UUID
    files: list[IngestFileSpec]


class IngestAssetUploadUrlResponse(BaseModel):
    model_config = _config_forbid()
    asset_id: UUID
    upload_url: str
    storage_key: str


class ManifestItemAnnotation(BaseModel):
    model_config = _config_forbid()
    schema: str
    data: dict


class ManifestItem(BaseModel):
    model_config = _config_forbid()
    type: str
    title: str | None = None
    summary: str | None = None
    payload: dict
    annotations: list[ManifestItemAnnotation] = Field(default_factory=list)


class Manifest(BaseModel):
    model_config = _config_forbid()
    items: list[ManifestItem]


class PublishRequest(BaseModel):
    model_config = _config_forbid()
    manifest: Manifest


class PublishResponse(BaseModel):
    model_config = _config_forbid()
    dataset_id: UUID
    status: str = "published"
    item_count: int


# ----- Validation errors (manifest publish) -----
class ManifestValidationErrorItem(BaseModel):
    model_config = _config_forbid()
    path: str  # e.g. "items[0]", "items[1].payload", "items[2].annotations[0]"
    error_type: str  # e.g. "extra_forbidden", "missing_required", "wrong_type", "invalid_ranking", "asset_not_uploaded"
    message: str


# ----- Admin: invites & shares -----
class CreateInviteRequest(BaseModel):
    model_config = _config_forbid()
    email: EmailStr
    role: str = "viewer"  # viewer | publisher


class InviteResponse(BaseModel):
    model_config = _config_forbid()
    invite_token: str
    expires_at: datetime


class DatasetShareEntry(BaseModel):
    model_config = _config_forbid()
    user_id: UUID | None = None  # null when pending (no account yet)
    email: str
    access_role: str
    created_at: datetime
    pending: bool = False  # true when shared with email that has no account yet


class AddShareRequest(BaseModel):
    model_config = _config_forbid()
    email: EmailStr
    access_role: str = "viewer"


# ----- Admin: audit viewer -----
class AuditEventEntry(BaseModel):
    model_config = _config_forbid()
    id: UUID
    org_id: UUID
    user_id: UUID
    event_type: str
    event_data: dict | None = None
    ip: str | None = None
    user_agent: str | None = None
    created_at: datetime


class AuditEventListResponse(BaseModel):
    model_config = _config_forbid()
    events: list[AuditEventEntry]
    next_offset: int | None = None  # pass as ?offset= for next page; null when no more
