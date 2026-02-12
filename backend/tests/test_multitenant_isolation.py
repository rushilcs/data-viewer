"""Multi-tenant isolation: Org A cannot access Org B resources. Prefer 404 over 403."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User, Dataset, Item, Asset
from app.core.security import hash_password


@pytest.fixture
async def publisher_client_org_a(client: AsyncClient, org_user):
    org, _ = org_user
    r = await client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": "password123"},
    )
    assert r.status_code == 200
    return client, r.json().get("csrf_token", "")


@pytest.fixture
async def org_b_resources(db: AsyncSession, other_org_user):
    """Create published dataset, item, and asset in Org B."""
    other_org, other_user = other_org_user
    ds_id = uuid4()
    asset_id = uuid4()
    item_id = uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=other_org.id,
        name="Org B Dataset",
        status="published",
        created_by_user_id=other_user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.flush()
    item = Item(
        id=item_id,
        org_id=other_org.id,
        dataset_id=ds_id,
        type="image_pair_compare",
        title="Org B Item",
        payload={"left_asset_id": str(asset_id), "right_asset_id": str(uuid4()), "prompt": "p"},
    )
    db.add(item)
    await db.flush()
    asset = Asset(
        id=asset_id,
        org_id=other_org.id,
        dataset_id=ds_id,
        item_id=item_id,
        kind="image",
        storage_key="orgb/x.png",
        content_type="image/png",
        byte_size=100,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(ds)
    await db.refresh(item)
    await db.refresh(asset)
    return other_org, other_user, ds_id, item_id, asset_id


@pytest.mark.asyncio
async def test_org_a_cannot_view_org_b_dataset(publisher_client_org_a, org_b_resources):
    """Org A must not see Org B's dataset (list or by ID). By ID returns 404."""
    client, csrf = publisher_client_org_a
    other_org, _, ds_id, _, _ = org_b_resources
    r = await client.get("/api/datasets")
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()]
    assert str(ds_id) not in ids
    r2 = await client.get(f"/api/datasets/{ds_id}")
    assert r2.status_code == 404
    assert "detail" in r2.json()


@pytest.mark.asyncio
async def test_org_a_cannot_view_org_b_items(publisher_client_org_a, org_b_resources):
    """Org A requesting Org B item by ID gets 404."""
    client, _ = publisher_client_org_a
    _, _, _, item_id, _ = org_b_resources
    r = await client.get(f"/api/items/{item_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_org_a_cannot_get_signed_url_for_org_b_asset(publisher_client_org_a, org_b_resources):
    """Org A requesting signed URL for Org B asset gets 404 (not 403)."""
    client, csrf = publisher_client_org_a
    _, _, _, _, asset_id = org_b_resources
    r = await client.post(
        f"/api/assets/{asset_id}/signed-url",
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 404
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_org_a_cannot_publish_org_b_dataset(publisher_client_org_a, org_b_resources):
    """Org A cannot publish Org B's dataset (404 when dataset is other org's)."""
    client, csrf = publisher_client_org_a
    _, _, ds_id, _, asset_id = org_b_resources
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={
            "manifest": {
                "items": [
                    {
                        "type": "image_pair_compare",
                        "payload": {
                            "left_asset_id": str(asset_id),
                            "right_asset_id": str(uuid4()),
                            "prompt": "p",
                        },
                    },
                ],
            },
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_org_a_cannot_upload_assets_to_org_b_dataset(publisher_client_org_a, org_b_resources):
    """Org A cannot upload assets to Org B dataset. Returns 404 (dataset not found to caller)."""
    client, csrf = publisher_client_org_a
    _, _, ds_id, _, _ = org_b_resources
    r = await client.post(
        "/api/ingest/assets:batch",
        json={
            "dataset_id": str(ds_id),
            "files": [{"filename": "x.png", "kind": "image", "content_type": "image/png", "byte_size": 10}],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_org_a_search_does_not_return_org_b_results(publisher_client_org_a, org_b_resources):
    """Org A's dataset items list / search must not include Org B items."""
    client, _ = publisher_client_org_a
    _, _, ds_id, item_id, _ = org_b_resources
    r = await client.get(f"/api/datasets/{ds_id}/items")
    assert r.status_code == 404
    r2 = await client.get(f"/api/datasets/{ds_id}/items?q=Org+B")
    assert r2.status_code == 404
    r3 = await client.get(f"/api/datasets/{ds_id}/item-type-counts")
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_cross_org_returns_404_not_403(publisher_client_org_a, org_b_resources):
    """Cross-org access must return 404 so we do not leak existence of other org's resources."""
    client, csrf = publisher_client_org_a
    _, _, ds_id, item_id, asset_id = org_b_resources
    for url in [
        f"/api/datasets/{ds_id}",
        f"/api/items/{item_id}",
        f"/api/assets/{asset_id}/signed-url",
    ]:
        if "signed-url" in url:
            r = await client.post(url, headers={"X-CSRF-Token": csrf})
        else:
            r = await client.get(url)
        assert r.status_code == 404, f"Expected 404 for {url}, got {r.status_code}"
        if r.status_code == 403:
            pytest.fail("Must not return 403 for cross-org (would leak existence)")
