"""E2E: login -> create draft -> upload assets -> publish -> list datasets/items -> item detail -> signed URL -> stream."""
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Dataset, Item, Asset
from app.core.config import get_settings


@pytest.fixture
async def publisher_client(client: AsyncClient, org_user):
    org, _ = org_user
    r = await client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": "password123"},
    )
    assert r.status_code == 200
    csrf = r.json().get("csrf_token", "")
    return client, csrf


@pytest.mark.asyncio
async def test_full_pipeline(publisher_client, db: AsyncSession):
    """Full pipeline: create draft, upload assets, publish, browse, mint signed URL, stream."""
    client, csrf = publisher_client

    # 1) Create draft dataset
    r = await client.post(
        "/api/ingest/datasets",
        json={"name": "E2E Dataset", "description": "E2E test"},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    data = r.json()
    dataset_id = data["dataset_id"]
    assert data["status"] == "draft"

    # 2) Batch upload URLs (two small "images")
    size = 12
    r = await client.post(
        "/api/ingest/assets:batch",
        json={
            "dataset_id": dataset_id,
            "files": [
                {"filename": "left.png", "kind": "image", "content_type": "image/png", "byte_size": size},
                {"filename": "right.png", "kind": "image", "content_type": "image/png", "byte_size": size},
            ],
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    batch = r.json()
    assert len(batch) == 2
    left_id = batch[0]["asset_id"]
    right_id = batch[1]["asset_id"]
    upload_url_left = batch[0]["upload_url"]
    upload_url_right = batch[1]["upload_url"]

    # 3) PUT upload (raw body)
    body = b"x" * size
    # Extract path and token from upload URL (e.g. http://test/api/ingest/assets/.../upload?token=...)
    path_left = "/api/ingest/assets/" + left_id + "/upload"
    token_left = upload_url_left.split("token=")[-1]
    r = await client.put(f"{path_left}?token={token_left}", content=body)
    assert r.status_code == 204

    path_right = "/api/ingest/assets/" + right_id + "/upload"
    token_right = upload_url_right.split("token=")[-1]
    r = await client.put(f"{path_right}?token={token_right}", content=body)
    assert r.status_code == 204

    # 4) Publish manifest
    manifest = {
        "items": [
            {
                "type": "image_pair_compare",
                "title": "E2E Pair",
                "summary": "Test pair",
                "payload": {
                    "left_asset_id": left_id,
                    "right_asset_id": right_id,
                    "prompt": "Compare these",
                },
            },
        ],
    }
    r = await client.post(
        f"/api/ingest/datasets/{dataset_id}/publish",
        json={"manifest": manifest},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "published"
    assert r.json()["item_count"] == 1

    # 5) Fetch dataset list
    r = await client.get("/api/datasets")
    assert r.status_code == 200
    datasets = r.json()
    ids = [d["id"] for d in datasets]
    assert dataset_id in ids

    # 6) Fetch items for dataset
    r = await client.get(f"/api/datasets/{dataset_id}/items")
    assert r.status_code == 200
    page = r.json()
    assert len(page["items"]) >= 1
    item_id = page["items"][0]["id"]

    # 7) Item detail
    r = await client.get(f"/api/items/{item_id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["item"]["type"] == "image_pair_compare"
    assert len(detail["assets"]) == 2

    # 8) Mint signed URL for one asset
    r = await client.post(
        f"/api/assets/{left_id}/signed-url",
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == 200
    signed = r.json()
    stream_url = signed["url"]

    # 9) Stream asset (extract path and token for same-origin request)
    path = "/api/assets/" + left_id + "/stream"
    token = stream_url.split("token=")[-1]
    r = await client.get(f"{path}?token={token}")
    assert r.status_code == 200
    assert r.content == body
