"""
Seed script for local dev: 2 orgs, 1 admin each, 1 published dataset per org
with 2-4 items (mixed types), placeholder assets in dev_assets/.
Run from backend/: python scripts/seed_dev.py
"""
import asyncio
import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Add parent to path so app is importable
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import Base, Organization, User, Dataset, Item, Asset, Annotation

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def create_placeholder_image(path: Path, w: int = 2, h: int = 2) -> None:
    """Write a minimal 1x1 PNG (valid) to path."""
    # Minimal valid PNG (1x1 red pixel)
    png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    assets_dir = Path(settings.dev_assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)

    async with async_session_factory() as db:
        # Check if already seeded
        r = await db.execute(select(Organization).limit(1))
        if r.scalar_one_or_none():
            print("Already seeded. Skip.")
            return

        org1_id = uuid.uuid4()
        org2_id = uuid.uuid4()
        o1 = Organization(id=org1_id, name="Verita")
        o2 = Organization(id=org2_id, name="Beta Inc")
        db.add_all([o1, o2])
        await db.flush()

        u1_id = uuid.uuid4()
        u2_id = uuid.uuid4()
        pw = hash_password("admin123")
        u1 = User(id=u1_id, org_id=org1_id, email="admin@verita.com", password_hash=pw, role="admin")
        u2 = User(id=u2_id, org_id=org2_id, email="admin@beta.com", password_hash=pw, role="admin")
        db.add_all([u1, u2])
        await db.flush()

        ds1_id = uuid.uuid4()
        ds2_id = uuid.uuid4()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        d1 = Dataset(
            id=ds1_id, org_id=org1_id, name="Verita Sample", description="Sample dataset",
            status="published", created_by_user_id=u1_id, published_at=now, tags=["sample"]
        )
        d2 = Dataset(
            id=ds2_id, org_id=org2_id, name="Beta Sample", description="Beta sample",
            status="published", created_by_user_id=u2_id, published_at=now, tags=["demo"]
        )
        db.add_all([d1, d2])
        await db.flush()

        def mk_key(prefix: str) -> str:
            return f"{prefix}_{uuid.uuid4().hex[:8]}.png"

        item1_id = uuid.uuid4()
        item2_id = uuid.uuid4()
        item3_id = uuid.uuid4()
        item4_id = uuid.uuid4()
        a1_left_id = uuid.uuid4()
        a1_right_id = uuid.uuid4()
        g1_id, g2_id, g3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        v_id = uuid.uuid4()
        aud_id = uuid.uuid4()

        # Items org1 (first so FKs exist for assets)
        item1 = Item(
            id=item1_id, org_id=org1_id, dataset_id=ds1_id, type="image_pair_compare",
            title="Compare A", summary="Left vs right",
            payload={"left_asset_id": str(a1_left_id), "right_asset_id": str(a1_right_id), "prompt": "Build a landing page", "metadata": {"model": "gpt-4"}},
        )
        item2 = Item(
            id=item2_id, org_id=org1_id, dataset_id=ds1_id, type="image_ranked_gallery",
            title="Gallery", summary="Ranked images",
            payload={"asset_ids": [str(g1_id), str(g2_id), str(g3_id)], "prompt": "Rank these", "rankings": {"method": "full_rank", "data": {"order": [str(g2_id), str(g1_id), str(g3_id)], "annotator_count": 3}}},
        )
        item3 = Item(
            id=item3_id, org_id=org1_id, dataset_id=ds1_id, type="video_with_timeline",
            title="Video", summary="Video with timeline",
            payload={"video_asset_id": str(v_id), "metadata": {"prompt": "Demo"}},
        )
        item4 = Item(
            id=item4_id, org_id=org1_id, dataset_id=ds1_id, type="audio_with_captions",
            title="Audio", summary="Audio with captions",
            payload={"audio_asset_id": str(aud_id), "metadata": {"language": "en-US"}},
        )
        db.add_all([item1, item2, item3, item4])
        await db.flush()

        # Assets org1: create files and DB rows
        a1_left_key = mk_key("left")
        a1_right_key = mk_key("right")
        create_placeholder_image(assets_dir / a1_left_key)
        create_placeholder_image(assets_dir / a1_right_key)
        g1_key, g2_key, g3_key = mk_key("g1"), mk_key("g2"), mk_key("g3")
        for k in (g1_key, g2_key, g3_key):
            create_placeholder_image(assets_dir / k)
        v_key, aud_key = mk_key("video"), mk_key("audio")
        create_placeholder_image(assets_dir / v_key)
        create_placeholder_image(assets_dir / aud_key)

        asset_rows_org1 = [
            Asset(id=a1_left_id, org_id=org1_id, dataset_id=ds1_id, item_id=item1_id, kind="image", storage_key=a1_left_key, content_type="image/png", byte_size=len((assets_dir / a1_left_key).read_bytes())),
            Asset(id=a1_right_id, org_id=org1_id, dataset_id=ds1_id, item_id=item1_id, kind="image", storage_key=a1_right_key, content_type="image/png", byte_size=len((assets_dir / a1_right_key).read_bytes())),
            Asset(id=g1_id, org_id=org1_id, dataset_id=ds1_id, item_id=item2_id, kind="image", storage_key=g1_key, content_type="image/png", byte_size=len((assets_dir / g1_key).read_bytes())),
            Asset(id=g2_id, org_id=org1_id, dataset_id=ds1_id, item_id=item2_id, kind="image", storage_key=g2_key, content_type="image/png", byte_size=len((assets_dir / g2_key).read_bytes())),
            Asset(id=g3_id, org_id=org1_id, dataset_id=ds1_id, item_id=item2_id, kind="image", storage_key=g3_key, content_type="image/png", byte_size=len((assets_dir / g3_key).read_bytes())),
            Asset(id=v_id, org_id=org1_id, dataset_id=ds1_id, item_id=item3_id, kind="video", storage_key=v_key, content_type="video/mp4", byte_size=len((assets_dir / v_key).read_bytes())),
            Asset(id=aud_id, org_id=org1_id, dataset_id=ds1_id, item_id=item4_id, kind="audio", storage_key=aud_key, content_type="audio/mpeg", byte_size=len((assets_dir / aud_key).read_bytes())),
        ]
        for ar in asset_rows_org1:
            db.add(ar)
        await db.flush()

        # Annotations for video and audio
        ann_v = Annotation(org_id=org1_id, dataset_id=ds1_id, item_id=item3_id, schema="timeline_v1", data={"events": []})
        ann_a = Annotation(org_id=org1_id, dataset_id=ds1_id, item_id=item4_id, schema="captions_v1", data={"segments": []})
        db.add_all([ann_v, ann_a])

        # Org2: one dataset with 2 items (pair + gallery)
        a2_left_key, a2_right_key = mk_key("o2_left"), mk_key("o2_right")
        create_placeholder_image(assets_dir / a2_left_key)
        create_placeholder_image(assets_dir / a2_right_key)
        a2_left_id = uuid.uuid4()
        a2_right_id = uuid.uuid4()
        o2_item1_id = uuid.uuid4()
        o2_item2_id = uuid.uuid4()
        db.add_all([
            Item(id=o2_item1_id, org_id=org2_id, dataset_id=ds2_id, type="image_pair_compare", title="Beta Compare", summary="Beta pair", payload={"left_asset_id": str(a2_left_id), "right_asset_id": str(a2_right_id), "prompt": "Beta prompt"}),
            Item(id=o2_item2_id, org_id=org2_id, dataset_id=ds2_id, type="image_ranked_gallery", title="Beta Gallery", summary="Beta gallery", payload={"asset_ids": [str(a2_left_id), str(a2_right_id)], "prompt": "Rank", "rankings": {"method": "scores", "data": {"scores": {str(a2_left_id): 0.8, str(a2_right_id): 0.6}, "scale": "0-1"}}}),
        ])
        await db.flush()
        db.add_all([
            Asset(id=a2_left_id, org_id=org2_id, dataset_id=ds2_id, item_id=o2_item1_id, kind="image", storage_key=a2_left_key, content_type="image/png", byte_size=100),
            Asset(id=a2_right_id, org_id=org2_id, dataset_id=ds2_id, item_id=o2_item1_id, kind="image", storage_key=a2_right_key, content_type="image/png", byte_size=100),
        ])
        await db.commit()
    print("Seed done. Users: admin@verita.com / admin@beta.com, password: admin123")


if __name__ == "__main__":
    asyncio.run(seed())
