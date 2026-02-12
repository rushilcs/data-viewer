"""Items: detail (payload + assets + annotations + normalized timeline/captions). Org-scoped."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_item_for_user
from app.db import get_db, Item, Asset, Annotation, User
from app.api.schemas import (
    ItemDetail,
    AssetMetadata,
    AnnotationOut,
    TimelineEventNormalized,
    CaptionSegmentNormalized,
)
from app.services.audit import log_audit

router = APIRouter(prefix="/items", tags=["items"])


def _normalize_timeline_events(events: list[dict]) -> list[TimelineEventNormalized]:
    out = []
    for ev in events:
        t_start = ev.get("t_start") or ev.get("start") or ev.get("time") or 0.0
        t_end = ev.get("t_end") or ev.get("end")
        if isinstance(t_start, (int, float)) and isinstance(t_end, (int, float)):
            pass
        elif isinstance(t_start, (int, float)):
            t_end = float(t_end) if t_end is not None else None
        else:
            t_start = float(t_start)
            t_end = float(t_end) if t_end is not None else None
        out.append(
            TimelineEventNormalized(
                t_start=float(t_start),
                t_end=float(t_end) if t_end is not None else None,
                label=ev.get("label"),
                metadata=ev.get("metadata"),
                track=ev.get("track"),
            )
        )
    return out


def _normalize_caption_segments(segments: list[dict]) -> list[CaptionSegmentNormalized]:
    out = []
    for seg in segments:
        t_start = seg.get("t_start") or seg.get("start") or 0.0
        t_end = seg.get("t_end") or seg.get("end")
        out.append(
            CaptionSegmentNormalized(
                t_start=float(t_start),
                t_end=float(t_end) if t_end is not None else None,
                text=seg.get("text"),
            )
        )
    return out


def _collect_asset_ids_from_payload(payload: dict) -> set[str]:
    """Extract asset_id / video_asset_id / audio_asset_id / asset_ids from payload."""
    ids = set()
    for key in ("left_asset_id", "right_asset_id", "video_asset_id", "poster_image_asset_id", "audio_asset_id"):
        v = payload.get(key)
        if v:
            ids.add(str(v))
    for aid in payload.get("asset_ids") or []:
        ids.add(str(aid))
    return ids


@router.get("/{item_id}", response_model=ItemDetail)
async def get_item(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = await get_item_for_user(item_id, user, db)
    asset_ids = _collect_asset_ids_from_payload(item.payload)
    assets_list = []
    if asset_ids:
        assets_result = await db.execute(
            select(Asset).where(
                Asset.org_id == user.org_id,
                Asset.id.in_([UUID(aid) for aid in asset_ids]),
            )
        )
        for a in assets_result.scalars().all():
            assets_list.append(AssetMetadata(id=a.id, kind=a.kind, content_type=a.content_type, byte_size=a.byte_size))
    ann_result = await db.execute(
        select(Annotation).where(
            Annotation.org_id == user.org_id,
            Annotation.item_id == item_id,
        )
    )
    ann_rows = list(ann_result.scalars().all())
    annotations = [AnnotationOut(schema=a.schema, data=a.data) for a in ann_rows]
    timeline_events = None
    caption_segments = None
    if item.type == "video_with_timeline":
        for a in ann_rows:
            if a.schema == "timeline_v1" and isinstance(a.data, dict):
                events = a.data.get("events") or []
                timeline_events = _normalize_timeline_events(events)
                break
    elif item.type == "audio_with_captions":
        for a in ann_rows:
            if a.schema == "captions_v1" and isinstance(a.data, dict):
                segs = a.data.get("segments") or []
                caption_segments = _normalize_caption_segments(
                    [{"t_start": s.get("start"), "t_end": s.get("end"), "text": s.get("text")} for s in segs]
                )
                break
    await log_audit(db, user.id, user.org_id, "view_item", event_data={"item_id": str(item_id)})
    return ItemDetail(
        item={
            "id": str(item.id),
            "type": item.type,
            "title": item.title,
            "summary": item.summary,
            "payload": item.payload,
            "created_at": item.created_at.isoformat(),
        },
        assets=assets_list,
        annotations=annotations,
        timeline_events=timeline_events,
        caption_segments=caption_segments,
    )