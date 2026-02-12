"""Dataset items filtering (q, type) and item-type-counts. Org-scoped."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User, Dataset, Item
from app.core.security import hash_password


@pytest.mark.asyncio
async def test_items_filter_by_type_and_q_org_scoped(client: AsyncClient, db: AsyncSession, org_user, other_org_user):
    org, user = org_user
    other_org, other_user = other_org_user
    ds_id = uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=org.id,
        name="My Dataset",
        status="published",
        created_by_user_id=user.id,
        published_at=datetime.now(timezone.utc),
        tags=["demo"],
    )
    db.add(ds)
    await db.flush()
    item_a = Item(
        id=uuid4(),
        org_id=org.id,
        dataset_id=ds_id,
        type="image_pair_compare",
        title="Alpha banana",
        summary="Has banana in title",
        payload={"left_asset_id": "x", "right_asset_id": "y", "prompt": "p"},
    )
    item_b = Item(
        id=uuid4(),
        org_id=org.id,
        dataset_id=ds_id,
        type="image_ranked_gallery",
        title="Beta",
        summary="Other",
        payload={"asset_ids": ["a", "b"], "prompt": "q", "rankings": {"method": "full_rank", "data": {"order": ["a", "b"], "annotator_count": 1}}},
    )
    db.add_all([item_a, item_b])
    await db.commit()

    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})

    r = await client.get(f"/api/datasets/{ds_id}/items?type=image_pair_compare")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "Alpha banana"

    r2 = await client.get(f"/api/datasets/{ds_id}/items?q=banana")
    assert r2.status_code == 200
    assert len(r2.json()["items"]) == 1
    assert "banana" in (r2.json()["items"][0].get("title") or "").lower() or "banana" in (r2.json()["items"][0].get("summary") or "").lower()

    r3 = await client.get(f"/api/datasets/{ds_id}/items?q=nonexistentxyz")
    assert r3.status_code == 200
    assert len(r3.json()["items"]) == 0


@pytest.mark.asyncio
async def test_item_type_counts_org_scoped_and_accurate(client: AsyncClient, db: AsyncSession, org_user, other_org_user):
    org, user = org_user
    other_org, other_user = other_org_user
    ds_id = uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=org.id,
        name="Counts Dataset",
        status="published",
        created_by_user_id=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.flush()
    for i in range(2):
        db.add(
            Item(
                id=uuid4(),
                org_id=org.id,
                dataset_id=ds_id,
                type="image_pair_compare",
                title=f"Pair {i}",
                payload={"left_asset_id": "a", "right_asset_id": "b", "prompt": "p"},
            )
        )
    for i in range(3):
        db.add(
            Item(
                id=uuid4(),
                org_id=org.id,
                dataset_id=ds_id,
                type="image_ranked_gallery",
                title=f"Gallery {i}",
                payload={"asset_ids": ["a", "b"], "prompt": "p", "rankings": {"method": "full_rank", "data": {"order": ["a", "b"], "annotator_count": 1}},
            )
        )
    await db.commit()

    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    r = await client.get(f"/api/datasets/{ds_id}/item-type-counts")
    assert r.status_code == 200
    data = r.json()
    assert data["counts"]["image_pair_compare"] == 2
    assert data["counts"]["image_ranked_gallery"] == 3
    assert data["total"] == 5

    other_ds_id = uuid4()
    other_ds = Dataset(
        id=other_ds_id,
        org_id=other_org.id,
        name="Other",
        status="published",
        created_by_user_id=other_user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(other_ds)
    await db.flush()
    db.add(
        Item(
            id=uuid4(),
            org_id=other_org.id,
            dataset_id=other_ds_id,
            type="image_pair_compare",
            title="Other",
            payload={"left_asset_id": "x", "right_asset_id": "y", "prompt": "p"},
        )
    )
    await db.commit()

    r2 = await client.get(f"/api/datasets/{other_ds_id}/item-type-counts")
    assert r2.status_code == 404
