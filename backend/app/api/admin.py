"""Admin: dataset sharing by email, audit viewer. Admin/publisher for shares; admin-only for audit."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_csrf, require_admin, require_admin_or_publisher, get_dataset_for_user
from app.db import get_db, User, DatasetAccess
from app.db.models import User as UserModel, PendingDatasetShare, AuditEvent
from app.api.schemas import DatasetShareEntry, AddShareRequest, AuditEventEntry, AuditEventListResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/datasets/{dataset_id}/shares", response_model=list[DatasetShareEntry])
async def list_dataset_shares(
    dataset_id: UUID,
    user: User = Depends(require_admin_or_publisher),
    db: AsyncSession = Depends(get_db),
):
    """List who has access: existing users (user_id set) and pending emails (pending=true)."""
    await get_dataset_for_user(dataset_id, user, db)
    out = []
    result = await db.execute(
        select(DatasetAccess, UserModel.email).join(
            UserModel, UserModel.id == DatasetAccess.user_id
        ).where(
            DatasetAccess.dataset_id == dataset_id,
            DatasetAccess.org_id == user.org_id,
        )
    )
    for da, email in result.all():
        out.append(DatasetShareEntry(user_id=da.user_id, email=email, access_role=da.access_role, created_at=da.created_at, pending=False))
    pending_result = await db.execute(
        select(PendingDatasetShare).where(
            PendingDatasetShare.dataset_id == dataset_id,
            PendingDatasetShare.org_id == user.org_id,
        )
    )
    for p in pending_result.scalars().all():
        out.append(DatasetShareEntry(user_id=None, email=p.email, access_role=p.access_role, created_at=p.created_at, pending=True))
    return out


@router.post("/datasets/{dataset_id}/shares", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
async def add_dataset_share(
    dataset_id: UUID,
    body: AddShareRequest,
    user: User = Depends(require_admin_or_publisher),
    db: AsyncSession = Depends(get_db),
):
    """Share dataset with email. If user exists in org, add dataset_access; else add pending (applied when they sign up). Idempotent."""
    await get_dataset_for_user(dataset_id, user, db)
    target = await db.execute(
        select(UserModel).where(
            UserModel.email == body.email,
            UserModel.org_id == user.org_id,
            UserModel.is_active == True,
        )
    )
    target_user = target.scalar_one_or_none()
    if target_user:
        existing = await db.execute(
            select(DatasetAccess).where(
                DatasetAccess.dataset_id == dataset_id,
                DatasetAccess.user_id == target_user.id,
            )
        )
        if existing.scalar_one_or_none():
            return
        da = DatasetAccess(
            org_id=user.org_id,
            dataset_id=dataset_id,
            user_id=target_user.id,
            access_role=body.access_role if body.access_role in ("viewer", "editor") else "viewer",
            created_by_user_id=user.id,
        )
        db.add(da)
    else:
        existing_pending = await db.execute(
            select(PendingDatasetShare).where(
                PendingDatasetShare.dataset_id == dataset_id,
                PendingDatasetShare.email == body.email,
            )
        )
        if existing_pending.scalar_one_or_none():
            return
        p = PendingDatasetShare(
            org_id=user.org_id,
            dataset_id=dataset_id,
            email=body.email,
            access_role=body.access_role if body.access_role in ("viewer", "editor") else "viewer",
            created_by_user_id=user.id,
        )
        db.add(p)
    await db.flush()


@router.delete("/datasets/{dataset_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
async def remove_dataset_share(
    dataset_id: UUID,
    user_id: UUID,
    user: User = Depends(require_admin_or_publisher),
    db: AsyncSession = Depends(get_db),
):
    """Remove dataset access for a user (by user_id)."""
    await get_dataset_for_user(dataset_id, user, db)
    result = await db.execute(
        select(DatasetAccess).where(
            DatasetAccess.dataset_id == dataset_id,
            DatasetAccess.user_id == user_id,
            DatasetAccess.org_id == user.org_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.delete(row)
    await db.flush()


@router.delete("/datasets/{dataset_id}/shares/pending", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
async def remove_pending_share(
    dataset_id: UUID,
    email: str,
    user: User = Depends(require_admin_or_publisher),
    db: AsyncSession = Depends(get_db),
):
    """Remove pending share (by email) for dataset."""
    await get_dataset_for_user(dataset_id, user, db)
    result = await db.execute(
        select(PendingDatasetShare).where(
            PendingDatasetShare.dataset_id == dataset_id,
            PendingDatasetShare.email == email,
            PendingDatasetShare.org_id == user.org_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.delete(row)
    await db.flush()


# ----- Audit viewer (admin only) -----
@router.get("/audit", response_model=AuditEventListResponse)
async def list_audit_events(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    event_type: str | None = Query(None, description="Filter by event_type"),
    org_id: UUID | None = Query(None, description="Filter by org_id"),
    user_id: UUID | None = Query(None, description="Filter by user_id"),
    from_time: datetime | None = Query(None, description="Events on or after (ISO datetime)"),
    to_time: datetime | None = Query(None, description="Events on or before (ISO datetime)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List audit events with optional filters and pagination. Admin only."""
    q = select(AuditEvent).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    if event_type is not None:
        q = q.where(AuditEvent.event_type == event_type)
    if org_id is not None:
        q = q.where(AuditEvent.org_id == org_id)
    if user_id is not None:
        q = q.where(AuditEvent.user_id == user_id)
    if from_time is not None:
        q = q.where(AuditEvent.created_at >= from_time.astimezone(timezone.utc))
    if to_time is not None:
        q = q.where(AuditEvent.created_at <= to_time.astimezone(timezone.utc))
    q = q.offset(offset).limit(limit + 1)
    result = await db.execute(q)
    rows = result.scalars().all()
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    events = [
        AuditEventEntry(
            id=r.id,
            org_id=r.org_id,
            user_id=r.user_id,
            event_type=r.event_type,
            event_data=r.event_data,
            ip=str(r.ip) if r.ip else None,
            user_agent=r.user_agent,
            created_at=r.created_at,
        )
        for r in rows
    ]
    next_offset = (offset + limit) if has_more else None
    return AuditEventListResponse(events=events, next_offset=next_offset)