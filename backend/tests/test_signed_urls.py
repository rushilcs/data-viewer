"""Signed URL (stream) token safety: HMAC, expiry, asset_id and org binding."""
import time
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User, Dataset, Asset
from app.core.security import hash_password, create_asset_stream_token, verify_asset_stream_token
from app.core.config import get_settings


# ----- Unit tests: verify_asset_stream_token -----


def test_stream_token_expired_rejected():
    """Expired stream token is rejected."""
    asset_id = uuid4()
    org_id = uuid4()
    token = create_asset_stream_token(asset_id, org_id)
    parts = token.rsplit(":", 1)
    msg, sig = parts[0], parts[1]
    # Set timestamp to past (issued long ago)
    past_ts = str(int(time.time()) - 400)
    import hmac
    import hashlib
    key = get_settings().secret_key.encode()
    old_msg = msg.rsplit(":", 1)[0] + ":" + past_ts
    old_sig = hmac.new(key, old_msg.encode(), hashlib.sha256).hexdigest()
    expired_token = f"{old_msg}:{old_sig}"
    assert verify_asset_stream_token(expired_token, asset_id, org_id) is False


def test_stream_token_modified_rejected():
    """Tampered token (wrong signature or modified message) is rejected."""
    asset_id = uuid4()
    org_id = uuid4()
    token = create_asset_stream_token(asset_id, org_id)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert verify_asset_stream_token(tampered, asset_id, org_id) is False
    tampered_msg = token.rsplit(":", 1)[0] + "x:" + token.rsplit(":", 1)[1]
    assert verify_asset_stream_token(tampered_msg, asset_id, org_id) is False


def test_stream_token_wrong_asset_id_rejected():
    """Token minted for asset A must not validate for asset B."""
    asset_a = uuid4()
    org_id = uuid4()
    token = create_asset_stream_token(asset_a, org_id)
    asset_b = uuid4()
    assert verify_asset_stream_token(token, asset_b, org_id) is False


def test_stream_token_wrong_org_id_rejected():
    """Token minted for org A must not validate for org B (same asset)."""
    asset_id = uuid4()
    org_a = uuid4()
    token = create_asset_stream_token(asset_id, org_a)
    org_b = uuid4()
    assert verify_asset_stream_token(token, asset_id, org_b) is False


# ----- Integration: stream endpoint returns 403 for bad token, 404 for wrong org -----


@pytest.mark.asyncio
async def test_stream_expired_token_403(client: AsyncClient, db: AsyncSession, org_user):
    """Stream with expired token returns 403."""
    org, user = org_user
    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    asset_id = uuid4()
    ds_id = uuid4()
    from datetime import datetime, timezone
    from app.db.models import Dataset
    ds = Dataset(id=ds_id, org_id=org.id, name="D", status="published", created_by_user_id=user.id, published_at=datetime.now(timezone.utc))
    db.add(ds)
    await db.flush()
    asset = Asset(
        id=asset_id,
        org_id=org.id,
        dataset_id=ds_id,
        kind="image",
        storage_key="dev/x.png",
        content_type="image/png",
        byte_size=10,
    )
    db.add(asset)
    assets_dir = Path(get_settings().dev_assets_dir)
    (assets_dir / "dev").mkdir(parents=True, exist_ok=True)
    (assets_dir / "dev" / "x.png").write_bytes(b"x" * 10)
    await db.commit()

    import hmac
    import hashlib
    key = get_settings().secret_key.encode()
    past_ts = int(time.time()) - 400
    msg = f"{asset_id}:{org.id}:{past_ts}"
    sig = hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()
    expired_token = f"{msg}:{sig}"

    r = await client.get(f"/api/assets/{asset_id}/stream?token={expired_token}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_stream_modified_token_403(client: AsyncClient, db: AsyncSession, org_user):
    """Stream with tampered token returns 403."""
    org, user = org_user
    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    asset_id = uuid4()
    ds_id = uuid4()
    from datetime import datetime, timezone
    from app.db.models import Dataset
    ds = Dataset(id=ds_id, org_id=org.id, name="D", status="published", created_by_user_id=user.id, published_at=datetime.now(timezone.utc))
    db.add(ds)
    await db.flush()
    asset = Asset(
        id=asset_id,
        org_id=org.id,
        dataset_id=ds_id,
        kind="image",
        storage_key="dev/y.png",
        content_type="image/png",
        byte_size=10,
    )
    db.add(asset)
    assets_dir = Path(get_settings().dev_assets_dir)
    (assets_dir / "dev").mkdir(parents=True, exist_ok=True)
    (assets_dir / "dev" / "y.png").write_bytes(b"y" * 10)
    await db.commit()

    token = create_asset_stream_token(asset_id, org.id)
    tampered = token + "x"

    r = await client.get(f"/api/assets/{asset_id}/stream?token={tampered}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_stream_wrong_asset_id_403(client: AsyncClient, db: AsyncSession, org_user):
    """Stream with token for asset A but request for asset B (same org) returns 403."""
    org, user = org_user
    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    asset_a = uuid4()
    asset_b = uuid4()
    ds_id = uuid4()
    from datetime import datetime, timezone
    from app.db.models import Dataset
    ds = Dataset(id=ds_id, org_id=org.id, name="D", status="published", created_by_user_id=user.id, published_at=datetime.now(timezone.utc))
    db.add(ds)
    await db.flush()
    for aid, name in [(asset_a, "a.png"), (asset_b, "b.png")]:
        a = Asset(id=aid, org_id=org.id, dataset_id=ds_id, kind="image", storage_key=f"dev/{name}", content_type="image/png", byte_size=10)
        db.add(a)
    assets_dir = Path(get_settings().dev_assets_dir)
    (assets_dir / "dev").mkdir(parents=True, exist_ok=True)
    (assets_dir / "dev" / "a.png").write_bytes(b"a" * 10)
    (assets_dir / "dev" / "b.png").write_bytes(b"b" * 10)
    await db.commit()

    token = create_asset_stream_token(asset_a, org.id)
    r = await client.get(f"/api/assets/{asset_b}/stream?token={token}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_stream_cross_org_404(client: AsyncClient, db: AsyncSession, org_user, other_org_user):
    """Stream for other org's asset returns 404 (no existence leak)."""
    org_a, user_a = org_user
    org_b, user_b = other_org_user
    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    asset_b = uuid4()
    ds_id = uuid4()
    from datetime import datetime, timezone
    from app.db.models import Dataset
    ds = Dataset(id=ds_id, org_id=org_b.id, name="D", status="published", created_by_user_id=user_b.id, published_at=datetime.now(timezone.utc))
    db.add(ds)
    await db.flush()
    asset = Asset(id=asset_b, org_id=org_b.id, dataset_id=ds_id, kind="image", storage_key="dev/c.png", content_type="image/png", byte_size=10)
    db.add(asset)
    await db.commit()

    token = create_asset_stream_token(asset_b, org_b.id)
    r = await client.get(f"/api/assets/{asset_b}/stream?token={token}")
    assert r.status_code == 404
