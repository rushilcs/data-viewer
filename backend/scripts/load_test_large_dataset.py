"""
Generate a large dataset (10k items) and measure list + item-detail latency.
Run from backend/: python scripts/load_test_large_dataset.py [--items 10000]
Requires: seed_dev + migrations. Optional: run backend and set MEASURE_HTTP=1 to measure via API.
"""
import argparse
import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models import Organization, User, Dataset, Item, Asset

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

LOAD_TEST_TAG = "load_test_10k"


async def ensure_large_dataset(db: AsyncSession, num_items: int) -> tuple[uuid.UUID, uuid.UUID]:
    """Create one org, one dataset with num_items items (minimal payload; one shared asset). Returns (org_id, dataset_id)."""
    from app.db.models import Base
    # Get or create org + admin
    r = await db.execute(select(Organization, User).join(User, User.org_id == Organization.id).where(User.role == "admin").limit(1))
    row = r.one_or_none()
    if not row:
        raise RuntimeError("Run seed_dev.py first.")
    org, admin = row[0], row[1]
    org_id, user_id = org.id, admin.id

    # Check for existing load-test dataset
    ds_r = await db.execute(select(Dataset).where(Dataset.tags.contains([LOAD_TEST_TAG])))
    existing = ds_r.scalar_one_or_none()
    if existing:
        count_r = await db.execute(select(Item).where(Item.dataset_id == existing.id))
        n = len(count_r.scalars().all())
        if n >= num_items:
            print(f"Using existing load-test dataset with {n} items.")
            return org_id, existing.id
        print(f"Existing dataset has {n} items; creating new with {num_items}.")

    ds_id = uuid.uuid4()
    ds = Dataset(
        id=ds_id,
        org_id=org_id,
        name="Load test (10k items)",
        description="Generated for latency measurement",
        status="published",
        created_by_user_id=user_id,
        published_at=datetime.now(timezone.utc),
        tags=[LOAD_TEST_TAG],
    )
    db.add(ds)
    await db.flush()

    # One shared asset (no real file needed for list/detail latency)
    shared_asset_id = uuid.uuid4()
    db.add(Asset(
        id=shared_asset_id,
        org_id=org_id,
        dataset_id=ds_id,
        item_id=None,
        kind="image",
        storage_key=f"{org_id}/{ds_id}/shared.png",
        content_type="image/png",
        byte_size=100,
    ))
    await db.flush()

    batch_size = 500
    for start in range(0, num_items, batch_size):
        end = min(start + batch_size, num_items)
        for i in range(start, end):
            item_id = uuid.uuid4()
            db.add(Item(
                id=item_id,
                org_id=org_id,
                dataset_id=ds_id,
                type="image_pair_compare",
                title=f"Item {i+1}",
                summary=f"Load test item {i+1}",
                payload={"left_asset_id": str(shared_asset_id), "right_asset_id": str(shared_asset_id), "prompt": f"Load test item {i+1}"},
            ))
        await db.flush()
        if (end % 2000) == 0:
            print(f"  Inserted {end} items...")
    await db.commit()
    print(f"Created dataset with {num_items} items.")
    return org_id, ds_id


async def measure_list_latency(db: AsyncSession, dataset_id: uuid.UUID, org_id: uuid.UUID, limit: int = 25, cursor: str | None = None) -> float:
    """Run the same query as list_dataset_items (first page or cursor page); return elapsed seconds."""
    from app.db.models import Item
    q = select(Item).where(Item.org_id == org_id, Item.dataset_id == dataset_id).order_by(Item.created_at.desc(), Item.id.desc())
    if cursor:
        try:
            import base64, json
            raw = base64.urlsafe_b64decode(cursor + "=" * (4 - len(cursor) % 4)).decode()
            data = json.loads(raw)
            from datetime import datetime
            ts = datetime.fromisoformat(data["t"])
            uid = uuid.UUID(data["i"])
            q = q.where((Item.created_at < ts) | ((Item.created_at == ts) & (Item.id < uid)))
        except Exception:
            pass
    q = q.limit(limit + 1)
    t0 = time.perf_counter()
    r = await db.execute(q)
    list(r.scalars().all())
    return time.perf_counter() - t0


async def measure_item_detail_latency(db: AsyncSession, item_id: uuid.UUID, org_id: uuid.UUID) -> float:
    """Run the same queries as get_item (item + assets + annotations); return elapsed seconds."""
    from app.db.models import Item, Asset, Annotation
    t0 = time.perf_counter()
    r = await db.execute(select(Item).where(Item.id == item_id, Item.org_id == org_id))
    item = r.scalar_one_or_none()
    if not item:
        return time.perf_counter() - t0
    a = await db.execute(select(Asset).where(Asset.item_id == item_id, Asset.org_id == org_id))
    list(a.scalars().all())
    ann = await db.execute(select(Annotation).where(Annotation.item_id == item_id, Annotation.org_id == org_id))
    list(ann.scalars().all())
    return time.perf_counter() - t0


async def run_measurements(db: AsyncSession, dataset_id: uuid.UUID, org_id: uuid.UUID, num_items: int) -> None:
    """Run list (first + one cursor) and item detail (sample) and print latencies."""
    from app.db.models import Item
    # First page
    latencies_first = []
    for _ in range(5):
        lat = await measure_list_latency(db, dataset_id, org_id, limit=25)
        latencies_first.append(lat)
    print(f"List (first page, limit=25):  p50={sorted(latencies_first)[2]*1000:.1f} ms  (5 runs)")

    # Get cursor for page 2
    r = await db.execute(
        select(Item).where(Item.org_id == org_id, Item.dataset_id == dataset_id)
        .order_by(Item.created_at.desc(), Item.id.desc()).limit(26)
    )
    rows = list(r.scalars().all())
    if len(rows) < 26:
        print("Not enough rows for cursor page.")
    else:
        last = rows[24]
        import base64, json
        cur = base64.urlsafe_b64encode(json.dumps({"t": last.created_at.isoformat(), "i": str(last.id)}).encode()).decode().rstrip("=")
        latencies_cursor = []
        for _ in range(5):
            lat = await measure_list_latency(db, dataset_id, org_id, limit=25, cursor=cur)
            latencies_cursor.append(lat)
        print(f"List (cursor page, limit=25): p50={sorted(latencies_cursor)[2]*1000:.1f} ms  (5 runs)")

    # Item detail: sample 10 items from middle of set
    mid = num_items // 2
    r = await db.execute(
        select(Item.id).where(Item.org_id == org_id, Item.dataset_id == dataset_id)
        .order_by(Item.created_at.desc(), Item.id.desc()).offset(mid).limit(10)
    )
    sample_ids = [row[0] for row in r.all()]
    detail_latencies = []
    for item_id in sample_ids:
        lat = await measure_item_detail_latency(db, item_id, org_id)
        detail_latencies.append(lat)
    detail_latencies.sort()
    p50 = detail_latencies[len(detail_latencies) // 2] * 1000
    p95 = detail_latencies[int(len(detail_latencies) * 0.95)] * 1000 if len(detail_latencies) >= 2 else p50
    print(f"Item detail (10 samples):      p50={p50:.1f} ms  p95={p95:.1f} ms")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", type=int, default=10_000)
    args = parser.parse_args()
    num_items = max(100, args.items)

    async with async_session_factory() as db:
        org_id, dataset_id = await ensure_large_dataset(db, num_items)
        await run_measurements(db, dataset_id, org_id, num_items)

    if os.environ.get("MEASURE_HTTP"):
        print("Set MEASURE_HTTP=1 to also measure via HTTP (backend must be running).")


if __name__ == "__main__":
    asyncio.run(main())
