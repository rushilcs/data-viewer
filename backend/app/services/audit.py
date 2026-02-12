"""Audit logging: login_success, view_dataset, view_item, mint_asset_url. Never log secrets."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent, User
from app.core.logging_redaction import redact_for_log


async def log_audit(
    db: AsyncSession,
    user_id: UUID,
    org_id: UUID,
    event_type: str,
    event_data: dict | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    safe_data = redact_for_log(event_data) if event_data else None
    event = AuditEvent(
        org_id=org_id,
        user_id=user_id,
        event_type=event_type,
        event_data=safe_data,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(event)
    await db.flush()
