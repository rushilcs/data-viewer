"""Ingestion: create draft, batch URLs, upload, publish validation and atomicity."""
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db import get_db
from app.db.models import Organization, User, Dataset, Item, Asset
from app.core.security import create_upload_token, verify_upload_token


@pytest.fixture
async def publisher_client(client: AsyncClient, org_user):
    org, user = org_user
    r = await client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": "password123"},
    )
    assert r.status_code == 200
    data = r.json()
    csrf = data.get("csrf_token")
    # Cookies are set in r.cookies; httpx AsyncClient sends them on same domain
    return client, csrf


@pytest.fixture
async def draft_with_assets(db: AsyncSession, org_user):
    org, user = org_user
    ds_id = uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=org.id,
        name="Draft",
        status="draft",
        created_by_user_id=user.id,
    )
    db.add(ds)
    await db.flush()
    a1 = uuid4()
    a2 = uuid4()
    db.add_all([
        Asset(id=a1, org_id=org.id, dataset_id=ds_id, kind="image", storage_key="d/x.png", content_type="image/png", byte_size=100),
        Asset(id=a2, org_id=org.id, dataset_id=ds_id, kind="image", storage_key="d/y.png", content_type="image/png", byte_size=100),
    ])
    await db.commit()
    return org, user, ds_id, a1, a2


@pytest.mark.asyncio
async def test_create_draft_requires_csrf(client: AsyncClient, org_user):
    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    r = await client.post(
        "/api/ingest/datasets",
        json={"name": "Test"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_create_draft_success(publisher_client, org_user):
    client, csrf = publisher_client
    r = await client.post(
        "/api/ingest/datasets",
        json={"name": "New Draft"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "draft"
    assert "dataset_id" in data


@pytest.mark.asyncio
async def test_viewer_cannot_create_draft(client: AsyncClient, db: AsyncSession, org_user):
    org, user = org_user
    user.role = "viewer"
    await db.commit()
    await db.refresh(user)
    r = await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    assert r.status_code == 200
    r2 = await client.post(
        "/api/ingest/datasets",
        json={"name": "X"},
        headers={"X-CSRF-Token": r.json().get("csrf_token", "")},
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_publish_invalid_payload_422(publisher_client, draft_with_assets):
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "payload": {
                    "left_asset_id": str(a1),
                    "right_asset_id": str(a2),
                    "prompt": "Ok",
                    "extra_field": "forbid",
                },
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_publish_missing_asset_422(publisher_client, draft_with_assets):
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "payload": {
                    "left_asset_id": str(a1),
                    "right_asset_id": str(uuid4()),
                    "prompt": "Ok",
                },
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    detail = r.json().get("detail", "")
    detail_str = str(detail) if isinstance(detail, (str, list)) else str(detail.get("errors", detail))
    assert "missing" in detail_str.lower() or "error" in detail_str.lower()


@pytest.mark.asyncio
async def test_publish_not_draft_404(db: AsyncSession, publisher_client, draft_with_assets):
    org, user, ds_id, a1, a2 = draft_with_assets
    result = await db.execute(select(Dataset).where(Dataset.id == ds_id))
    ds = result.scalar_one()
    ds.status = "published"
    ds.published_at = datetime.now(timezone.utc)
    await db.commit()
    client, csrf = publisher_client
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "payload": {"left_asset_id": str(a1), "right_asset_id": str(a2), "prompt": "Ok"},
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_publish_success_atomic(db: AsyncSession, publisher_client, draft_with_assets):
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "title": "Pair",
                "payload": {"left_asset_id": str(a1), "right_asset_id": str(a2), "prompt": "Ok"},
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "published"
    assert data["item_count"] == 1
    # Check DB
    res = await db.execute(select(Item).where(Item.dataset_id == ds_id))
    items = res.scalars().all()
    assert len(items) == 1
    assert items[0].type == "image_pair_compare"
    res_ds = await db.execute(select(Dataset).where(Dataset.id == ds_id))
    ds = res_ds.scalar_one()
    assert ds.status == "published"


def test_upload_token_expired_rejected():
    """Unit test: verify_upload_token returns False for expired token."""
    a_id = uuid4()
    org_id = uuid4()
    ds_id = uuid4()
    import time
    token = create_upload_token(a_id, org_id, ds_id, 10)
    parts = token.rsplit(":", 1)
    msg = parts[0]
    import hmac
    import hashlib
    from app.core.config import get_settings
    key = get_settings().secret_key.encode()
    expired_msg = msg.rsplit(":", 1)[0] + ":0"
    expired_sig = hmac.new(key, expired_msg.encode(), hashlib.sha256).hexdigest()
    expired_token = f"{expired_msg}:{expired_sig}"
    assert verify_upload_token(expired_token, a_id, org_id, ds_id, 10) is False


def test_upload_token_wrong_asset_rejected():
    """Unit test: verify_upload_token returns False for wrong asset_id."""
    a_id = uuid4()
    org_id = uuid4()
    ds_id = uuid4()
    token = create_upload_token(a_id, org_id, ds_id, 10)
    assert verify_upload_token(token, uuid4(), org_id, ds_id, 10) is False


# ----- Strict validation (Part 1) -----


@pytest.mark.asyncio
async def test_publish_unknown_field_in_payload_422(publisher_client, draft_with_assets):
    """Unknown fields in payload are rejected (extra=forbid)."""
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "payload": {
                    "left_asset_id": str(a1),
                    "right_asset_id": str(a2),
                    "prompt": "Ok",
                    "unknown_field": "forbidden",
                },
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    detail = r.json().get("detail", {})
    errors = detail.get("errors", []) if isinstance(detail, dict) else []
    assert any("extra" in str(e).lower() or "path" in str(e) for e in errors) or "payload" in str(detail)


@pytest.mark.asyncio
async def test_publish_missing_required_field_422(publisher_client, draft_with_assets):
    """Missing required payload field returns path and error type."""
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "payload": {"left_asset_id": str(a1), "right_asset_id": str(a2)},
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422
    detail = r.json().get("detail", {})
    errors = detail.get("errors", []) if isinstance(detail, dict) else []
    assert len(errors) >= 1
    if isinstance(errors[0], dict):
        assert "path" in errors[0] or "message" in errors[0]


@pytest.mark.asyncio
async def test_publish_wrong_type_422(publisher_client, draft_with_assets):
    """Wrong type in payload (e.g. asset_id as int) returns 422."""
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "payload": {
                    "left_asset_id": 123,
                    "right_asset_id": str(a2),
                    "prompt": "Ok",
                },
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_publish_invalid_ranking_structure_422(publisher_client, draft_with_assets):
    """Invalid rankings shape (e.g. full_rank with wrong data) returns 422."""
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_ranked_gallery",
                "payload": {
                    "asset_ids": [str(a1), str(a2)],
                    "prompt": "Rank these",
                    "rankings": {"method": "full_rank", "data": {"order": [str(a1)], "annotator_count": "not_an_int"}},
                },
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_publish_empty_manifest_400(publisher_client, draft_with_assets):
    """Empty manifest returns 400."""
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": {"items": []}},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 400
    assert "one item" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_publish_twice_409(db, publisher_client, draft_with_assets):
    """Publishing an already published dataset returns 409."""
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "payload": {"left_asset_id": str(a1), "right_asset_id": str(a2), "prompt": "Ok"},
            },
        ],
    }
    r1 = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r1.status_code == 200
    r2 = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r2.status_code == 409
    assert "already published" in r2.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_upload_assets_to_published_dataset_409(db, publisher_client, draft_with_assets):
    """Uploading assets to a published dataset returns 409."""
    client, csrf = publisher_client
    org, user, ds_id, a1, a2 = draft_with_assets
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "payload": {"left_asset_id": str(a1), "right_asset_id": str(a2), "prompt": "Ok"},
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{ds_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    r2 = await client.post(
        f"/api/ingest/assets:batch",
        json={
            "dataset_id": str(ds_id),
            "files": [{"filename": "x.png", "kind": "image", "content_type": "image/png", "byte_size": 10}],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r2.status_code == 409
    assert "published" in r2.json().get("detail", "").lower()
