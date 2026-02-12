"""Datasets: list, detail, items (cursor-paginated, filtered), item-type-counts. All org-scoped."""
import base64
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, cast, Text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_dataset_for_user
from app.db import get_db, Dataset, Item, User, DatasetAccess
from app.api.schemas import DatasetSummary, DatasetDetail, ItemSummary, PaginatedItems, ItemTypeCounts
from app.services.audit import log_audit


def _encode_cursor(created_at: datetime, item_id: UUID) -> str:
    """Opaque cursor for keyset pagination: (created_at, id)."""
    raw = json.dumps({"t": created_at.isoformat(), "i": str(item_id)})
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime | None, UUID | None]:
    """Decode cursor to (created_at, item_id); returns (None, None) if invalid."""
    try:
        padded = cursor + "=" * (4 - len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        data = json.loads(raw)
        return datetime.fromisoformat(data["t"]), UUID(data["i"])
    except (ValueError, KeyError, TypeError):
        return None, None

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetSummary])
async def list_datasets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Admin/publisher: all datasets in org. Viewer: only datasets with dataset_access row.
    if user.role in ("admin", "publisher"):
        q = select(Dataset).where(Dataset.org_id == user.org_id)
    else:
        q = (
            select(Dataset)
            .join(DatasetAccess, (DatasetAccess.dataset_id == Dataset.id) & (DatasetAccess.user_id == user.id))
            .where(Dataset.org_id == user.org_id)
        )
    q = q.order_by(Dataset.created_at.desc())
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        DatasetSummary(
            id=r.id,
            name=r.name,
            description=r.description,
            status=r.status,
            created_at=r.created_at,
            published_at=r.published_at,
            tags=r.tags or [],
        )
        for r in rows
    ]


@router.get("/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(
    dataset_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await get_dataset_for_user(dataset_id, user, db)
    await log_audit(db, user.id, user.org_id, "view_dataset", event_data={"dataset_id": str(dataset_id)})
    return DatasetDetail(
        id=row.id,
        name=row.name,
        description=row.description,
        status=row.status,
        created_at=row.created_at,
        published_at=row.published_at,
        tags=row.tags or [],
        created_by_user_id=row.created_by_user_id,
    )


@router.get("/{dataset_id}/items", response_model=PaginatedItems)
async def list_dataset_items(
    dataset_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    type_filter: str | None = Query(None, alias="type"),
    tag: str | None = None,
    q: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: int = Query(25, ge=1, le=100),
    cursor: str | None = None,
):
    dataset = await get_dataset_for_user(dataset_id, user, db)
    if dataset.status != "published":
        return PaginatedItems(items=[], next_cursor=None, has_more=False)
    query = select(Item).where(Item.org_id == user.org_id, Item.dataset_id == dataset_id)
    if type_filter:
        query = query.where(Item.type == type_filter)
    if tag:
        if not dataset.tags or tag not in dataset.tags:
            return PaginatedItems(items=[], next_cursor=None, has_more=False)
    if q and q.strip():
        from app.services.search import apply_search_filter
        query = apply_search_filter(query, q.strip())
    if created_after is not None:
        query = query.where(Item.created_at >= created_after)
    if created_before is not None:
        query = query.where(Item.created_at <= created_before)
    # Keyset (cursor) pagination: (created_at, id) for stable, index-friendly pages
    cursor_ts, cursor_id = _decode_cursor(cursor) if cursor else (None, None)
    if cursor_ts is not None and cursor_id is not None:
        query = query.where(
            (Item.created_at < cursor_ts) | ((Item.created_at == cursor_ts) & (Item.id < cursor_id))
        )
    query = query.order_by(Item.created_at.desc(), Item.id.desc()).limit(limit + 1)
    items_result = await db.execute(query)
    items = list(items_result.scalars().all())
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
    last = items[-1] if items else None
    next_cursor = _encode_cursor(last.created_at, last.id) if has_more and last else None
    return PaginatedItems(
        items=[
            ItemSummary(id=i.id, type=i.type, title=i.title, summary=i.summary, created_at=i.created_at)
            for i in items
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{dataset_id}/item-type-counts", response_model=ItemTypeCounts)
async def get_item_type_counts(
    dataset_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await get_dataset_for_user(dataset_id, user, db)
    if dataset.status != "published":
        return ItemTypeCounts(counts={}, total=0)
    count_q = select(Item.type, func.count(Item.id)).where(
        Item.org_id == user.org_id,
        Item.dataset_id == dataset_id,
    ).group_by(Item.type)
    count_result = await db.execute(count_q)
    rows = count_result.all()
    counts = {row[0]: row[1] for row in rows}
    total = sum(counts.values())
    return ItemTypeCounts(counts=counts, total=total)
