"""Pytest fixtures: test client, DB, test user."""
import asyncio
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.db.models import Base, Organization, User, Dataset, Item, Asset
from app.core.security import hash_password
from app.db.session import get_db

TEST_DATABASE_URL = "postgresql+asyncpg://viewer:viewer@localhost:5433/viewer_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        yield session


@pytest.fixture
async def client(db):
    async def get_db_override():
        yield db
    app.dependency_overrides[get_db] = get_db_override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def org_user(db: AsyncSession):
    org_id = uuid4()
    user_id = uuid4()
    org = Organization(id=org_id, name="Test Org")
    user = User(
        id=user_id,
        org_id=org_id,
        email="test@test.com",
        password_hash=hash_password("password123"),
        role="admin",
    )
    db.add(org)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)
    return org, user


@pytest.fixture
async def other_org_user(db: AsyncSession):
    """Another org/user for cross-org tests."""
    org_id = uuid4()
    user_id = uuid4()
    org = Organization(id=org_id, name="Other Org")
    user = User(
        id=user_id,
        org_id=org_id,
        email="other@other.com",
        password_hash=hash_password("other123"),
        role="admin",
    )
    db.add(org)
    db.add(user)
    await db.commit()
    await db.refresh(org)
    await db.refresh(user)
    return org, user
