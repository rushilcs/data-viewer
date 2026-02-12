"""
Item type registry: validate_payload and extract_asset_ids per docs/03-item-schemas.md.
Pydantic models with extra="forbid".
"""
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field, model_validator

# --- Ranking data shapes (for image_ranked_gallery) ---


class FullRankData(BaseModel):
    order: list[str]  # asset_id strings
    annotator_count: int

    model_config = {"extra": "forbid"}


class ScoresData(BaseModel):
    scores: dict[str, float]
    scale: str

    model_config = {"extra": "forbid"}


class PairwiseData(BaseModel):
    model_config = {"extra": "forbid"}


class RankingsPayload(BaseModel):
    method: str = Field(..., pattern="^(pairwise|full_rank|scores)$")
    data: dict[str, Any]  # FullRankData | ScoresData | PairwiseData validated below

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def validate_data_shape(self) -> "RankingsPayload":
        if self.method == "full_rank":
            FullRankData.model_validate(self.data)
        elif self.method == "scores":
            ScoresData.model_validate(self.data)
        return self


# --- Item payloads ---


class ImagePairComparePayload(BaseModel):
    left_asset_id: UUID
    right_asset_id: UUID
    prompt: str
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}

    @staticmethod
    def extract_asset_ids(payload: dict) -> list[UUID]:
        p = ImagePairComparePayload.model_validate(payload)
        return [p.left_asset_id, p.right_asset_id]


class ImageRankedGalleryPayload(BaseModel):
    asset_ids: list[UUID] = Field(..., min_length=2)
    prompt: str
    rankings: RankingsPayload
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}

    @staticmethod
    def extract_asset_ids(payload: dict) -> list[UUID]:
        p = ImageRankedGalleryPayload.model_validate(payload)
        return list(p.asset_ids)


class VideoWithTimelinePayload(BaseModel):
    video_asset_id: UUID
    poster_image_asset_id: UUID | None = None
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}

    @staticmethod
    def extract_asset_ids(payload: dict) -> list[UUID]:
        p = VideoWithTimelinePayload.model_validate(payload)
        out = [p.video_asset_id]
        if p.poster_image_asset_id:
            out.append(p.poster_image_asset_id)
        return out


class AudioWithCaptionsPayload(BaseModel):
    audio_asset_id: UUID
    metadata: dict[str, Any] | None = None

    model_config = {"extra": "forbid"}

    @staticmethod
    def extract_asset_ids(payload: dict) -> list[UUID]:
        p = AudioWithCaptionsPayload.model_validate(payload)
        return [p.audio_asset_id]


# --- Annotation schemas ---


class TimelineV1Data(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class CaptionsV1Segment(BaseModel):
    start: float | None = None
    end: float | None = None
    text: str | None = None

    model_config = {"extra": "forbid"}


class CaptionsV1Data(BaseModel):
    segments: list[CaptionsV1Segment] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


def validate_annotation(schema: str, data: dict) -> None:
    if schema == "timeline_v1":
        TimelineV1Data.model_validate(data)
    elif schema == "captions_v1":
        CaptionsV1Data.model_validate(data)
    else:
        raise ValueError(f"Unknown annotation schema: {schema}")


# --- Registry ---


def validate_payload(item_type: str, payload: dict) -> dict:
    """Validate payload for item_type; return validated payload (as dict). Raises pydantic.ValidationError."""
    reg = _ITEM_TYPE_REGISTRY.get(item_type)
    if not reg:
        raise ValueError(f"Unsupported item type: {item_type}")
    model = reg["model"]
    validated = model.model_validate(payload)
    return validated.model_dump(mode="json")


def extract_asset_ids(item_type: str, payload: dict) -> list[UUID]:
    """Return list of asset UUIDs referenced by payload."""
    reg = _ITEM_TYPE_REGISTRY.get(item_type)
    if not reg:
        raise ValueError(f"Unsupported item type: {item_type}")
    return reg["extract_asset_ids"](payload)


def get_supported_item_types() -> list[str]:
    return list(_ITEM_TYPE_REGISTRY.keys())


_ITEM_TYPE_REGISTRY: dict[str, dict[str, Any]] = {
    "image_pair_compare": {
        "model": ImagePairComparePayload,
        "extract_asset_ids": lambda p: ImagePairComparePayload.extract_asset_ids(p),
    },
    "image_ranked_gallery": {
        "model": ImageRankedGalleryPayload,
        "extract_asset_ids": lambda p: ImageRankedGalleryPayload.extract_asset_ids(p),
    },
    "video_with_timeline": {
        "model": VideoWithTimelinePayload,
        "extract_asset_ids": lambda p: VideoWithTimelinePayload.extract_asset_ids(p),
    },
    "audio_with_captions": {
        "model": AudioWithCaptionsPayload,
        "extract_asset_ids": lambda p: AudioWithCaptionsPayload.extract_asset_ids(p),
    },
}
