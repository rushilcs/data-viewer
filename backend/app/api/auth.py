"""Auth: login, logout, me, signup (open). Cookie-based JWT + CSRF."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user, require_csrf
from app.core.rate_limit import is_login_rate_limited
from app.core.security import (
    create_access_token,
    create_csrf_token,
    hash_password,
    verify_password,
)
from app.db import get_db, User
from app.db.models import User as UserModel, Organization, PendingDatasetShare, DatasetAccess
from app.api.schemas import LoginRequest, SignupRequest, UserProfile
from app.services.audit import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _cookie_params(secure: bool | None = None, samesite: str | None = None) -> dict:
    secure = secure if secure is not None else settings.cookie_secure
    samesite = samesite or settings.cookie_samesite
    return {
        "httponly": True,
        "samesite": samesite,
        "path": "/",
        "max_age": settings.access_token_expire_minutes * 60,
        "secure": secure,
    }


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    if is_login_rate_limited(body.email):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")
    result = await db.execute(
        select(UserModel).where(UserModel.email == body.email, UserModel.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    from app.db.models import Organization
    org_row = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org_obj = org_row.scalar_one()
    access_token = create_access_token(str(user.id), str(user.org_id))
    csrf_token = create_csrf_token()
    response.set_cookie(key=settings.cookie_name, value=access_token, **_cookie_params())
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=3600 * 24,
        secure=settings.cookie_secure,
    )
    await log_audit(
        db,
        user.id,
        user.org_id,
        "login_success",
        event_data={"email": body.email},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"user": UserProfile(id=user.id, email=user.email, org_id=user.org_id, org_name=org_obj.name, role=user.role), "csrf_token": csrf_token}


async def _resolve_signup_org(db: AsyncSession, email: str) -> UUID:
    """Org for new user: org from first pending share for this email, else default_org_id or first org."""
    pending = await db.execute(
        select(PendingDatasetShare.org_id).where(PendingDatasetShare.email == email).limit(1)
    )
    row = pending.scalar_one_or_none()
    if row is not None:
        return row[0] if hasattr(row, "__getitem__") else row
    if getattr(settings, "default_org_id", None):
        try:
            return UUID(settings.default_org_id)
        except (ValueError, TypeError):
            pass
    first = await db.execute(select(Organization.id).order_by(Organization.id).limit(1))
    first_row = first.scalar_one_or_none()
    if not first_row:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No organization configured")
    return first_row[0] if hasattr(first_row, "__getitem__") else first_row


@router.post("/signup")
async def signup(
    request: Request,
    response: Response,
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    """Open signup: create account with email+password. User joins org from pending shares or default org. Pending shares for that email are applied so they see shared datasets."""
    existing = await db.execute(select(UserModel).where(UserModel.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    org_id = await _resolve_signup_org(db, body.email)
    from uuid import uuid4
    user_id = uuid4()
    user = UserModel(
        id=user_id,
        org_id=org_id,
        email=body.email,
        password_hash=hash_password(body.password),
        role="viewer",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    pending_rows = await db.execute(
        select(PendingDatasetShare).where(
            PendingDatasetShare.org_id == org_id,
            PendingDatasetShare.email == body.email,
        )
    )
    for p in pending_rows.scalars().all():
        da = DatasetAccess(
            org_id=p.org_id,
            dataset_id=p.dataset_id,
            user_id=user.id,
            access_role=p.access_role,
            created_by_user_id=p.created_by_user_id,
        )
        db.add(da)
        await db.delete(p)
    await db.flush()
    org_row = await db.execute(select(Organization).where(Organization.id == org_id))
    org_obj = org_row.scalar_one()
    access_token = create_access_token(str(user.id), str(user.org_id))
    csrf_token = create_csrf_token()
    response.set_cookie(key=settings.cookie_name, value=access_token, **_cookie_params())
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite=settings.cookie_samesite,
        path="/",
        max_age=3600 * 24,
        secure=settings.cookie_secure,
    )
    await log_audit(
        db,
        user.id,
        user.org_id,
        "signup",
        event_data={"email": body.email},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"user": UserProfile(id=user.id, email=user.email, org_id=user.org_id, org_name=org_obj.name, role=user.role), "csrf_token": csrf_token}


@router.post("/logout", dependencies=[Depends(require_csrf)])
async def logout(response: Response):
    response.delete_cookie(settings.cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.db.models import Organization
    org_row = await db.execute(select(Organization).where(Organization.id == user.org_id))
    org = org_row.scalar_one()
    return UserProfile(id=user.id, email=user.email, org_id=user.org_id, org_name=org.name, role=user.role)
