"""
Delete datasets whose name matches a pattern (e.g. "web design preference").
Removes annotations, assets, items, dataset_access, pending_dataset_share, then the dataset.
Run from backend/: python scripts/delete_datasets_by_name.py "web design preference"
"""
import asyncio
import os
import sys

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db.models import (
    Base,
    Dataset,
    Item,
    Asset,
    Annotation,
    DatasetAccess,
    PendingDatasetShare,
)

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main(name_pattern: str) -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Dataset).where(Dataset.name.ilike(f"%{name_pattern}%"))
        )
        datasets = result.scalars().all()
        if not datasets:
            print(f"No datasets matching '{name_pattern}' found.")
            return
        for ds in datasets:
            print(f"Deleting dataset: {ds.name} (id={ds.id})")
            await db.execute(delete(Annotation).where(Annotation.dataset_id == ds.id))
            await db.execute(delete(Asset).where(Asset.dataset_id == ds.id))
            await db.execute(delete(Item).where(Item.dataset_id == ds.id))
            await db.execute(delete(PendingDatasetShare).where(PendingDatasetShare.dataset_id == ds.id))
            await db.execute(delete(DatasetAccess).where(DatasetAccess.dataset_id == ds.id))
            await db.execute(delete(Dataset).where(Dataset.id == ds.id))
        await db.commit()
        print(f"Deleted {len(datasets)} dataset(s).")


if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "web design preference"
    asyncio.run(main(pattern))
