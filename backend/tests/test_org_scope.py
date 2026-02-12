"""Org scoping: datasets and items return 404 for other org."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User, Dataset, Item
from app.core.security import hash_password, create_access_token
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_datasets_only_own_org(client: AsyncClient, db: AsyncSession, org_user, other_org_user):
    org, user = org_user
    other_org, other_user = other_org_user
    # Create dataset for other_org
    ds_id = uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=other_org.id,
        name="Other Dataset",
        description="",
        status="published",
        created_by_user_id=other_user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.commit()

    # Login as first org
    await client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": "password123"},
    )
    r = await client.get("/api/datasets")
    assert r.status_code == 200
    ids = [d["id"] for d in r.json()]
    assert str(ds_id) not in ids

    # Access other org's dataset by ID -> 404
    r2 = await client.get(f"/api/datasets/{ds_id}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_items_404_other_org(client: AsyncClient, db: AsyncSession, org_user, other_org_user):
    org, user = org_user
    other_org, other_user = other_org_user
    ds_id = uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=other_org.id,
        name="Other",
        status="published",
        created_by_user_id=other_user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.flush()
    item_id = uuid4()
    item = Item(
        id=item_id,
        org_id=other_org.id,
        dataset_id=ds_id,
        type="image_pair_compare",
        title="Other Item",
        payload={"left_asset_id": "x", "right_asset_id": "y", "prompt": "p"},
    )
    db.add(item)
    await db.commit()

    await client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": "password123"},
    )
    r = await client.get(f"/api/items/{item_id}")
    assert r.status_code == 404
