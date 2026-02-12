"""Security regression: IDOR, share/invite abuse, signed-URL abuse. All must return 404 for unauthorized resource access (no enumeration)."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.logging_redaction import redact_for_log


def test_redact_for_log_redacts_sensitive_keys():
    """Audit/log must never contain passwords or tokens."""
    out = redact_for_log({"email": "u@x.com", "password": "secret123", "token": "jwt.here"})
    assert out["email"] == "u@x.com"
    assert out["password"] == "[REDACTED]"
    assert out["token"] == "[REDACTED]"


def test_redact_for_log_nested():
    out = redact_for_log({"data": {"access_token": "xyz", "name": "ok"}})
    assert out["data"]["access_token"] == "[REDACTED]"
    assert out["data"]["name"] == "ok"


def test_redact_for_log_jwt_like_string():
    out = redact_for_log({"payload": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"})
    assert out["payload"] == "[REDACTED]"
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User, Dataset, Item, Asset, DatasetAccess
from app.core.security import hash_password


@pytest.fixture
async def two_datasets_same_org(db: AsyncSession):
    """Org with admin, viewer with access only to dataset A; dataset B exists but not shared to viewer."""
    org_id = uuid4()
    admin_id = uuid4()
    viewer_id = uuid4()
    org = Organization(id=org_id, name="Org")
    admin = User(id=admin_id, org_id=org_id, email="admin@o.com", password_hash=hash_password("a"), role="admin")
    viewer = User(id=viewer_id, org_id=org_id, email="viewer@o.com", password_hash=hash_password("v"), role="viewer")
    ds_a = uuid4()
    ds_b = uuid4()
    dA = Dataset(id=ds_a, org_id=org_id, name="A", status="published", created_by_user_id=admin_id, published_at=datetime.now(timezone.utc))
    dB = Dataset(id=ds_b, org_id=org_id, name="B", status="published", created_by_user_id=admin_id, published_at=datetime.now(timezone.utc))
    item_b = uuid4()
    asset_b = uuid4()
    itemB = Item(id=item_b, org_id=org_id, dataset_id=ds_b, type="image_pair_compare", title="B", payload={"left_asset_id": str(asset_b), "right_asset_id": str(uuid4()), "prompt": "p"})
    assetB = Asset(id=asset_b, org_id=org_id, dataset_id=ds_b, item_id=item_b, kind="image", storage_key="b/x.png", content_type="image/png", byte_size=10)
    db.add(org)
    db.add(admin)
    db.add(viewer)
    db.add(dA)
    db.add(dB)
    db.add(itemB)
    db.add(assetB)
    da = DatasetAccess(org_id=org_id, dataset_id=ds_a, user_id=viewer_id, access_role="viewer", created_by_user_id=admin_id)
    db.add(da)
    await db.commit()
    return {"admin": admin, "viewer": viewer, "ds_a": ds_a, "ds_b": ds_b, "item_b": item_b, "asset_b": asset_b}


@pytest.mark.asyncio
async def test_idor_viewer_cannot_access_unshared_dataset_same_org(client: AsyncClient, two_datasets_same_org):
    """Viewer with access only to ds_a must get 404 for ds_b (same org)."""
    data = two_datasets_same_org
    await client.post("/api/auth/login", json={"email": "viewer@o.com", "password": "v"})
    r = await client.get(f"/api/datasets/{data['ds_b']}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_idor_viewer_cannot_access_unshared_item_same_org(client: AsyncClient, two_datasets_same_org):
    """Viewer must get 404 for item in unshared dataset (same org)."""
    data = two_datasets_same_org
    await client.post("/api/auth/login", json={"email": "viewer@o.com", "password": "v"})
    r = await client.get(f"/api/items/{data['item_b']}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_idor_viewer_cannot_mint_signed_url_unshared_asset_same_org(client: AsyncClient, two_datasets_same_org):
    """Viewer must get 404 when minting signed URL for asset in unshared dataset (same org)."""
    data = two_datasets_same_org
    login = await client.post("/api/auth/login", json={"email": "viewer@o.com", "password": "v"})
    csrf = login.json().get("csrf_token") or "x"
    r = await client.post(f"/api/assets/{data['asset_b']}/signed-url", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_share_abuse_viewer_cannot_add_share(client: AsyncClient, two_datasets_same_org):
    """Viewer cannot add shares (403)."""
    data = two_datasets_same_org
    login = await client.post("/api/auth/login", json={"email": "viewer@o.com", "password": "v"})
    csrf = login.json().get("csrf_token") or "x"
    r = await client.post(
        f"/api/admin/datasets/{data['ds_a']}/shares",
        json={"email": "someone@o.com", "access_role": "viewer"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_share_abuse_viewer_cannot_remove_share(client: AsyncClient, two_datasets_same_org):
    """Viewer cannot remove shares (403)."""
    data = two_datasets_same_org
    login = await client.post("/api/auth/login", json={"email": "viewer@o.com", "password": "v"})
    csrf = login.json().get("csrf_token") or "x"
    r = await client.delete(
        f"/api/admin/datasets/{data['ds_a']}/shares/{data['admin'].id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_share_abuse_admin_cannot_share_other_org_dataset(client: AsyncClient, db: AsyncSession, two_datasets_same_org):
    """Admin of org A gets 404 when trying to share a dataset that belongs to org B (IDOR)."""
    data = two_datasets_same_org
    # Create org B and a dataset in B
    org_b_id = uuid4()
    user_b_id = uuid4()
    org_b = Organization(id=org_b_id, name="Org B")
    user_b = User(id=user_b_id, org_id=org_b_id, email="b@b.com", password_hash=hash_password("b"), role="admin")
    ds_b_org = uuid4()
    d = Dataset(id=ds_b_org, org_id=org_b_id, name="B DS", status="published", created_by_user_id=user_b_id, published_at=datetime.now(timezone.utc))
    db.add(org_b)
    db.add(user_b)
    db.add(d)
    await db.commit()
    # Org A admin tries to add share to Org B's dataset
    login = await client.post("/api/auth/login", json={"email": "admin@o.com", "password": "a"})
    csrf = login.json().get("csrf_token") or "x"
    r = await client.post(
        f"/api/admin/datasets/{ds_b_org}/shares",
        json={"email": "any@b.com", "access_role": "viewer"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_signed_url_abuse_cross_org_404(client: AsyncClient, db: AsyncSession):
    """User in org A must get 404 (not 403) when requesting signed URL for asset in org B."""
    org_a = uuid4()
    org_b = uuid4()
    u_a = uuid4()
    u_b = uuid4()
    db.add(Organization(id=org_a, name="A"))
    db.add(Organization(id=org_b, name="B"))
    db.add(User(id=u_a, org_id=org_a, email="a@a.com", password_hash=hash_password("a"), role="admin"))
    db.add(User(id=u_b, org_id=org_b, email="b@b.com", password_hash=hash_password("b"), role="admin"))
    ds_b = uuid4()
    asset_b = uuid4()
    item_b = uuid4()
    db.add(Dataset(id=ds_b, org_id=org_b, name="B", status="published", created_by_user_id=u_b, published_at=datetime.now(timezone.utc)))
    db.add(Item(id=item_b, org_id=org_b, dataset_id=ds_b, type="image_pair_compare", title="B", payload={"left_asset_id": str(asset_b), "right_asset_id": str(uuid4()), "prompt": "p"}))
    db.add(Asset(id=asset_b, org_id=org_b, dataset_id=ds_b, item_id=item_b, kind="image", storage_key="b/x.png", content_type="image/png", byte_size=10))
    await db.commit()
    login = await client.post("/api/auth/login", json={"email": "a@a.com", "password": "a"})
    csrf = login.json().get("csrf_token") or "x"
    r = await client.post(f"/api/assets/{asset_b}/signed-url", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 404
    assert "detail" in r.json()
