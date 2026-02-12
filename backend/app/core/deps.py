"""FastAPI dependencies: DB, current user, CSRF, org-scoped lookups."""
from uuid import UUID

from fastapi import Cookie, Header, Request, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token, verify_csrf_token
from app.db import get_db, User, Dataset, Item, Asset, DatasetAccess
from app.core.config import get_settings

settings = get_settings()

NOT_FOUND = "Not found"


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
    cookie: str | None = Cookie(None, alias=settings.cookie_name),
) -> User | None:
    """Return current user if valid JWT in cookie; else None (no 401)."""
    token = cookie
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload or "org_id" not in payload:
        return None
    sub = payload["sub"]
    org_id = payload["org_id"]
    result = await db.execute(
        select(User).where(
            User.id == UUID(sub),
            User.org_id == UUID(org_id),
            User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()
    return user


async def get_current_user(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
) -> User:
    """Require authenticated user; 401 if not."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_csrf(
    request: Request,
    csrf_cookie: str | None = Cookie(None, alias=settings.csrf_cookie_name),
    csrf_header: str | None = Header(None, alias=settings.csrf_header_name),
) -> None:
    """Validate CSRF for state-changing methods. Raise 403 if invalid."""
    if not verify_csrf_token(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )


def require_publisher(user: User = Depends(get_current_user)) -> User:
    """Require user role admin or publisher for ingestion."""
    if user.role not in ("admin", "publisher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Publisher or admin role required",
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin role (metrics, audit viewer, etc.)."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def require_admin_or_publisher(user: User = Depends(get_current_user)) -> User:
    """Require admin or publisher for invites and sharing."""
    if user.role not in ("admin", "publisher"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or publisher role required",
        )
    return user


def require_metrics_access(
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    x_metrics_secret: str | None = Header(None, alias="X-Metrics-Secret"),
) -> None:
    """Allow /metrics if: admin (when metrics_require_admin), or valid X-Metrics-Secret, or no guard (local)."""
    s = get_settings()
    if s.metrics_require_admin:
        if user is None or user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Metrics require admin authentication",
            )
        return
    if s.metrics_secret:
        if x_metrics_secret != s.metrics_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-Metrics-Secret",
            )
        return
    # No guard (e.g. local dev with metrics_require_admin=False and no secret)
    return


# ----- Org-scoped lookups (404 on missing / wrong org) -----


async def get_dataset_for_user(
    dataset_id: UUID, user: User, db: AsyncSession
) -> Dataset:
    """Return dataset if user has access; else raise 404. Admin/publisher: all org datasets. Viewer: only if dataset_access row exists."""
    result = await db.execute(
        select(Dataset).where(Dataset.id == dataset_id, Dataset.org_id == user.org_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    if user.role in ("admin", "publisher"):
        return row
    # Viewer: must have explicit dataset_access
    access_result = await db.execute(
        select(DatasetAccess).where(
            DatasetAccess.dataset_id == dataset_id,
            DatasetAccess.user_id == user.id,
            DatasetAccess.org_id == user.org_id,
        )
    )
    if not access_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return row


async def get_item_for_user(item_id: UUID, user: User, db: AsyncSession) -> Item:
    """Return item if it belongs to user's org and user has dataset access; else raise 404."""
    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.org_id == user.org_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    await get_dataset_for_user(row.dataset_id, user, db)
    return row


async def get_asset_for_user(asset_id: UUID, user: User, db: AsyncSession) -> Asset:
    """Return asset if it belongs to user's org and user has dataset access; else raise 404."""
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id, Asset.org_id == user.org_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    await get_dataset_for_user(row.dataset_id, user, db)
    return row
