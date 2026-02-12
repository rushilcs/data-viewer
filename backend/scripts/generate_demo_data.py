"""
Generate deterministic demo datasets with realistic items/assets/annotations.
Run from backend/: python scripts/generate_demo_data.py [--seed 42] [--items-per-dataset 50]
Creates N datasets per org, ~items_per_dataset items (mixed types), PNGs via Pillow, sample video/audio.
"""
import argparse
import asyncio
import os
import random
import struct
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models import Base, Organization, User, Dataset, Item, Asset, Annotation

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Backend dir so asset paths work regardless of script cwd
BACKEND_DIR = Path(__file__).resolve().parent.parent
# Sample directory for reusable video/audio
SAMPLES_DIR = BACKEND_DIR / "dev_assets_samples"

def make_minimal_wav(path: Path, duration_sec: float = 2.0) -> None:
    """Write a minimal valid WAV (8kHz mono, 16-bit) - actually audible silence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 8000
    n_samples = int(sample_rate * duration_sec)
    data = b"\x00\x00" * n_samples
    size = len(data) + 36
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", size))
        f.write(b"WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", len(data)))
        f.write(data)


def make_minimal_mp4(path: Path) -> None:
    """Write a minimal MP4 file (valid ftyp box so browsers accept it; may not play)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal MP4: ftyp + small mdat so Content-Type works; some players may play it
    minimal = (
        b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41"
        b"\x00\x00\x00\x10mdat\x00\x00\x00\x00\x00\x00\x00\x00"
    )
    path.write_bytes(minimal)


def create_png_with_text(path: Path, text: str, width: int = 320, height: int = 240) -> None:
    """Create a PNG with text overlay using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color=(240, 240, 245))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    draw.text((10, height // 2 - 10), text[:80], fill=(60, 60, 80), font=font)
    img.save(path, "PNG")


async def run(seed_val: int, items_per_dataset: int):
    random.seed(seed_val)
    # Use absolute path so files land in backend/dev_assets regardless of script cwd
    assets_dir = (BACKEND_DIR / "dev_assets").resolve()
    assets_dir.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    sample_wav = SAMPLES_DIR / "sample.wav"
    sample_mp4 = SAMPLES_DIR / "sample.mp4"
    if not sample_wav.exists():
        make_minimal_wav(sample_wav)
    if not sample_mp4.exists():
        make_minimal_mp4(sample_mp4)

    async with async_session_factory() as db:
        # Remove existing demo datasets (same seed would recreate same IDs and cause duplicate key)
        demo_ds = await db.execute(select(Dataset.id).where(Dataset.tags.contains(["demo"])))
        demo_ids = [r[0] for r in demo_ds.all()]
        if demo_ids:
            await db.execute(delete(Annotation).where(Annotation.dataset_id.in_(demo_ids)))
            await db.execute(delete(Asset).where(Asset.dataset_id.in_(demo_ids)))
            await db.execute(delete(Item).where(Item.dataset_id.in_(demo_ids)))
            await db.execute(delete(Dataset).where(Dataset.id.in_(demo_ids)))
            await db.flush()

        orgs_result = await db.execute(select(Organization, User).join(User, User.org_id == Organization.id).where(User.role == "admin"))
        rows = orgs_result.all()
        if not rows:
            print("Run seed_dev.py first to create orgs and users.")
            return

        for org, admin_user in rows:
            org_id = org.id
            for ds_idx in range(3):
                ds_id = uuid.UUID(int=random.getrandbits(128))
                ds_name = f"Demo Dataset {ds_idx + 1} ({org.name})"
                ds = Dataset(
                    id=ds_id,
                    org_id=org_id,
                    name=ds_name,
                    description=f"Generated demo with {items_per_dataset} items",
                    status="published",
                    created_by_user_id=admin_user.id,
                    published_at=datetime.now(timezone.utc),
                    tags=["demo", "generated", f"set{ds_idx}"],
                )
                db.add(ds)
                await db.flush()

                n_items = min(max(items_per_dataset, 25), 100)
                item_types = ["image_pair_compare", "image_ranked_gallery", "video_with_timeline", "audio_with_captions"]
                type_cycle = [item_types[i % 4] for i in range(n_items)]
                random.shuffle(type_cycle)

                for i, itype in enumerate(type_cycle):
                    item_id = uuid.uuid4()
                    title = f"Item {i+1} ({itype})"
                    summary = f"Generated {itype} item"
                    payload = {}
                    if itype == "image_pair_compare":
                        left_id, right_id = uuid.uuid4(), uuid.uuid4()
                        left_key = f"{org_id}/{ds_id}/{left_id}.png"
                        right_key = f"{org_id}/{ds_id}/{right_id}.png"
                        left_path = assets_dir / left_key
                        right_path = assets_dir / right_key
                        create_png_with_text(left_path, f"Left: {title}")
                        create_png_with_text(right_path, f"Right: {title}")
                        payload = {"left_asset_id": str(left_id), "right_asset_id": str(right_id), "prompt": f"Compare: {title}", "metadata": {"gen": "demo"}}
                        db.add(Item(id=item_id, org_id=org_id, dataset_id=ds_id, type=itype, title=title, summary=summary, payload=payload))
                        await db.flush()
                        for aid, key, path in [(left_id, left_key, left_path), (right_id, right_key, right_path)]:
                            db.add(Asset(id=aid, org_id=org_id, dataset_id=ds_id, item_id=item_id, kind="image", storage_key=key, content_type="image/png", byte_size=path.stat().st_size))
                    elif itype == "image_ranked_gallery":
                        n_imgs = random.randint(2, 5)
                        asset_ids = [uuid.uuid4() for _ in range(n_imgs)]
                        order = [str(aid) for aid in asset_ids]
                        random.shuffle(order)
                        payload = {"asset_ids": [str(a) for a in asset_ids], "prompt": f"Rank: {title}", "rankings": {"method": "full_rank", "data": {"order": order, "annotator_count": 3}}, "metadata": {}}
                        db.add(Item(id=item_id, org_id=org_id, dataset_id=ds_id, type=itype, title=title, summary=summary, payload=payload))
                        await db.flush()
                        for j, aid in enumerate(asset_ids):
                            key = f"{org_id}/{ds_id}/{aid}.png"
                            p = assets_dir / key
                            create_png_with_text(p, f"Gallery {i+1} img {j+1}")
                            db.add(Asset(id=aid, org_id=org_id, dataset_id=ds_id, item_id=item_id, kind="image", storage_key=key, content_type="image/png", byte_size=p.stat().st_size))
                    elif itype == "video_with_timeline":
                        vid_id = uuid.uuid4()
                        key = f"{org_id}/{ds_id}/{vid_id}.mp4"
                        dest = assets_dir / key
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        import shutil
                        shutil.copy(sample_mp4, dest)
                        payload = {"video_asset_id": str(vid_id), "metadata": {"title": title}}
                        db.add(Item(id=item_id, org_id=org_id, dataset_id=ds_id, type=itype, title=title, summary=summary, payload=payload))
                        await db.flush()
                        db.add(Asset(id=vid_id, org_id=org_id, dataset_id=ds_id, item_id=item_id, kind="video", storage_key=key, content_type="video/mp4", byte_size=dest.stat().st_size))
                        events = [{"t_start": t, "t_end": t + 0.5, "label": f"Event at {t}s", "track": "default"} for t in [0.0, 1.0, 2.0, 3.0]]
                        db.add(Annotation(org_id=org_id, dataset_id=ds_id, item_id=item_id, schema="timeline_v1", data={"events": events}))
                    else:
                        aud_id = uuid.uuid4()
                        key = f"{org_id}/{ds_id}/{aud_id}.wav"
                        dest = assets_dir / key
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        import shutil
                        shutil.copy(sample_wav, dest)
                        payload = {"audio_asset_id": str(aud_id), "metadata": {"language": "en-US"}}
                        db.add(Item(id=item_id, org_id=org_id, dataset_id=ds_id, type=itype, title=title, summary=summary, payload=payload))
                        await db.flush()
                        db.add(Asset(id=aud_id, org_id=org_id, dataset_id=ds_id, item_id=item_id, kind="audio", storage_key=key, content_type="audio/wav", byte_size=dest.stat().st_size))
                        segs = [{"start": 0.0, "end": 0.5, "text": "First phrase."}, {"start": 0.5, "end": 1.0, "text": "Second phrase."}]
                        db.add(Annotation(org_id=org_id, dataset_id=ds_id, item_id=item_id, schema="captions_v1", data={"segments": segs}))
                    await db.flush()

        await db.commit()
    print(f"Demo data generated (seed={seed_val}, items_per_dataset={items_per_dataset}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--items-per-dataset", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(run(args.seed, args.items_per_dataset))
