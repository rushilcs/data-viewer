"""Item detail returns normalized timeline_events and caption_segments for video/audio."""
import pytest
from uuid import uuid4
from datetime import datetime, timezone

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, User, Dataset, Item, Annotation
from app.core.security import hash_password


@pytest.mark.asyncio
async def test_item_detail_video_returns_normalized_timeline_events(client: AsyncClient, db: AsyncSession, org_user):
    org, user = org_user
    ds_id = uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=org.id,
        name="V",
        status="published",
        created_by_user_id=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.flush()
    item_id = uuid4()
    vid_id = uuid4()
    db.add(
        Item(
            id=item_id,
            org_id=org.id,
            dataset_id=ds_id,
            type="video_with_timeline",
            title="Video",
            payload={"video_asset_id": str(vid_id), "metadata": {}},
        )
    )
    await db.flush()
    db.add(
        Annotation(
            org_id=org.id,
            dataset_id=ds_id,
            item_id=item_id,
            schema="timeline_v1",
            data={
                "events": [
                    {"time": 0, "label": "Start"},
                    {"t_start": 5.0, "t_end": 6.0, "label": "Middle", "track": "default"},
                ]
            },
        )
    )
    await db.commit()

    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    r = await client.get(f"/api/items/{item_id}")
    assert r.status_code == 200
    data = r.json()
    assert "timeline_events" in data
    events = data["timeline_events"]
    assert events is not None
    assert len(events) == 2
    assert events[0]["t_start"] == 0.0
    assert events[0]["label"] == "Start"
    assert events[1]["t_start"] == 5.0
    assert events[1]["t_end"] == 6.0
    assert events[1]["track"] == "default"


@pytest.mark.asyncio
async def test_item_detail_audio_returns_normalized_caption_segments(client: AsyncClient, db: AsyncSession, org_user):
    org, user = org_user
    ds_id = uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=org.id,
        name="A",
        status="published",
        created_by_user_id=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db.add(ds)
    await db.flush()
    item_id = uuid4()
    aud_id = uuid4()
    db.add(
        Item(
            id=item_id,
            org_id=org.id,
            dataset_id=ds_id,
            type="audio_with_captions",
            title="Audio",
            payload={"audio_asset_id": str(aud_id), "metadata": {}},
        )
    )
    await db.flush()
    db.add(
        Annotation(
            org_id=org.id,
            dataset_id=ds_id,
            item_id=item_id,
            schema="captions_v1",
            data={"segments": [{"start": 0.0, "end": 1.0, "text": "Hello."}, {"start": 1.0, "end": 2.0, "text": "World."}]},
        )
    )
    await db.commit()

    await client.post("/api/auth/login", json={"email": "test@test.com", "password": "password123"})
    r = await client.get(f"/api/items/{item_id}")
    assert r.status_code == 200
    data = r.json()
    assert "caption_segments" in data
    segs = data["caption_segments"]
    assert segs is not None
    assert len(segs) == 2
    assert segs[0]["t_start"] == 0.0
    assert segs[0]["t_end"] == 1.0
    assert segs[0]["text"] == "Hello."
    assert segs[1]["text"] == "World."
