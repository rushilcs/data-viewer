"""Dataset sharing + open signup: viewer ACL, share by email (existing or pending)."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User, Dataset, Item, Asset, PendingDatasetShare
from app.core.security import hash_password


@pytest.fixture
async def org_admin_viewer_and_dataset(db: AsyncSession):
    """Org with admin, viewer (no dataset_access yet), and one published dataset with an item/asset."""
    org_id = uuid4()
    admin_id = uuid4()
    viewer_id = uuid4()
    org = Organization(id=org_id, name="Verita")
    admin = User(
        id=admin_id,
        org_id=org_id,
        email="admin@verita.com",
        password_hash=hash_password("admin123"),
        role="admin",
    )
    viewer = User(
        id=viewer_id,
        org_id=org_id,
        email="viewer@verita.com",
        password_hash=hash_password("view123"),
        role="viewer",
    )
    ds_id = uuid4()
    dataset = Dataset(
        id=ds_id,
        org_id=org_id,
        name="Shared DS",
        description=None,
        status="published",
        created_by_user_id=admin_id,
        published_at=datetime.now(timezone.utc),
    )
    item_id = uuid4()
    item = Item(
        id=item_id,
        org_id=org_id,
        dataset_id=ds_id,
        type="image_pair_compare",
        title="Test",
        summary=None,
        payload={"left_asset_id": "", "right_asset_id": "", "prompt": "x"},
    )
    asset_id = uuid4()
    asset = Asset(
        id=asset_id,
        org_id=org_id,
        dataset_id=ds_id,
        item_id=item_id,
        kind="image",
        storage_key="org/ds/file.png",
        content_type="image/png",
        byte_size=100,
    )
    db.add(org)
    db.add(admin)
    db.add(viewer)
    db.add(dataset)
    db.add(item)
    db.add(asset)
    await db.commit()
    await db.refresh(dataset)
    await db.refresh(admin)
    await db.refresh(viewer)
    return {
        "org_id": org_id,
        "admin": admin,
        "viewer": viewer,
        "dataset": dataset,
        "item": item,
        "asset": asset,
    }


async def test_viewer_cannot_list_unshared_datasets(client: AsyncClient, org_admin_viewer_and_dataset):
    """Viewer sees no datasets until one is shared."""
    data = org_admin_viewer_and_dataset
    await client.post("/api/auth/login", json={"email": "viewer@verita.com", "password": "view123"})
    r = await client.get("/api/datasets")
    assert r.status_code == 200
    assert r.json() == []


async def test_viewer_gets_404_on_unshared_dataset(client: AsyncClient, org_admin_viewer_and_dataset):
    """Direct URL to unshared dataset returns 404 for viewer."""
    data = org_admin_viewer_and_dataset
    ds_id = str(data["dataset"].id)
    await client.post("/api/auth/login", json={"email": "viewer@verita.com", "password": "view123"})
    r = await client.get(f"/api/datasets/{ds_id}")
    assert r.status_code == 404


async def test_viewer_gets_404_on_unshared_item(client: AsyncClient, org_admin_viewer_and_dataset):
    """Viewer cannot access item in unshared dataset."""
    data = org_admin_viewer_and_dataset
    item_id = str(data["item"].id)
    await client.post("/api/auth/login", json={"email": "viewer@verita.com", "password": "view123"})
    r = await client.get(f"/api/items/{item_id}")
    assert r.status_code == 404


async def test_viewer_gets_404_for_asset_signed_url_unshared(client: AsyncClient, org_admin_viewer_and_dataset):
    """Viewer cannot mint signed URL for asset in unshared dataset."""
    data = org_admin_viewer_and_dataset
    asset_id = str(data["asset"].id)
    await client.post("/api/auth/login", json={"email": "viewer@verita.com", "password": "view123"})
    r = await client.post(f"/api/assets/{asset_id}/signed-url", headers={"X-CSRF-Token": "x"})
    assert r.status_code == 404


async def test_admin_shares_dataset_viewer_then_sees_it(client: AsyncClient, org_admin_viewer_and_dataset):
    """Admin adds dataset_access for viewer; viewer can then list and access dataset."""
    data = org_admin_viewer_and_dataset
    ds_id = str(data["dataset"].id)
    viewer_email = data["viewer"].email
    login_r = await client.post("/api/auth/login", json={"email": "admin@verita.com", "password": "admin123"})
    csrf = login_r.json().get("csrf_token") or "x"
    r = await client.post(
        f"/api/admin/datasets/{ds_id}/shares",
        json={"email": viewer_email, "access_role": "viewer"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code in (201, 200)
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    await client.post("/api/auth/login", json={"email": "viewer@verita.com", "password": "view123"})
    r = await client.get("/api/datasets")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "Shared DS"
    r2 = await client.get(f"/api/datasets/{ds_id}")
    assert r2.status_code == 200


async def test_open_signup_creates_user(client: AsyncClient, org_admin_viewer_and_dataset):
    """Open signup with email+password creates user and returns session."""
    r = await client.post("/api/auth/signup", json={"email": "newuser@verita.com", "password": "securepass123"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["email"] == "newuser@verita.com"
    assert body["user"]["role"] == "viewer"
    assert "csrf_token" in body


async def test_share_with_nonexistent_email_creates_pending_then_signup_sees_dataset(
    client: AsyncClient, org_admin_viewer_and_dataset
):
    """Share with email that has no account creates pending; when they sign up they see the dataset."""
    data = org_admin_viewer_and_dataset
    ds_id = str(data["dataset"].id)
    login_r = await client.post("/api/auth/login", json={"email": "admin@verita.com", "password": "admin123"})
    csrf = login_r.json().get("csrf_token") or "x"
    r = await client.post(
        f"/api/admin/datasets/{ds_id}/shares",
        json={"email": "futureuser@verita.com", "access_role": "viewer"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 201
    shares = await client.get(f"/api/admin/datasets/{ds_id}/shares")
    assert shares.status_code == 200
    assert len(shares.json()) == 1
    assert shares.json()[0]["email"] == "futureuser@verita.com"
    assert shares.json()[0]["pending"] is True
    await client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    signup_r = await client.post("/api/auth/signup", json={"email": "futureuser@verita.com", "password": "pass123"})
    assert signup_r.status_code == 200
    ds_list = await client.get("/api/datasets")
    assert ds_list.status_code == 200
    assert len(ds_list.json()) == 1
    assert ds_list.json()[0]["name"] == "Shared DS"


async def test_viewer_cannot_add_share(client: AsyncClient, org_admin_viewer_and_dataset):
    """Viewer cannot add dataset share (no access to admin shares endpoint)."""
    data = org_admin_viewer_and_dataset
    ds_id = str(data["dataset"].id)
    await client.post("/api/auth/login", json={"email": "viewer@verita.com", "password": "view123"})
    r = await client.post(
        f"/api/admin/datasets/{ds_id}/shares",
        json={"email": "other@verita.com", "access_role": "viewer"},
        headers={"X-CSRF-Token": "x"},
    )
    assert r.status_code == 403


async def test_admin_list_shares(client: AsyncClient, org_admin_viewer_and_dataset):
    """Admin can list shares; after adding one, it appears."""
    data = org_admin_viewer_and_dataset
    ds_id = str(data["dataset"].id)
    login_r = await client.post("/api/auth/login", json={"email": "admin@verita.com", "password": "admin123"})
    csrf = login_r.json().get("csrf_token") or "x"
    r = await client.get(f"/api/admin/datasets/{ds_id}/shares")
    assert r.status_code == 200
    assert r.json() == []
    await client.post(
        f"/api/admin/datasets/{ds_id}/shares",
        json={"email": "viewer@verita.com", "access_role": "viewer"},
        headers={"X-CSRF-Token": csrf},
    )
    r2 = await client.get(f"/api/admin/datasets/{ds_id}/shares")
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["email"] == "viewer@verita.com"


async def test_add_share_with_nonexistent_email_creates_pending(client: AsyncClient, org_admin_viewer_and_dataset):
    """Adding share for email that is not a user creates pending (201), not 404."""
    data = org_admin_viewer_and_dataset
    ds_id = str(data["dataset"].id)
    login_r = await client.post("/api/auth/login", json={"email": "admin@verita.com", "password": "admin123"})
    csrf = login_r.json().get("csrf_token") or "x"
    r = await client.post(
        f"/api/admin/datasets/{ds_id}/shares",
        json={"email": "nobody@verita.com", "access_role": "viewer"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 201
