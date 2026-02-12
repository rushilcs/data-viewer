"""Auth: login, me, logout, 401."""
import pytest
from httpx import AsyncClient

from app.db.models import User
from app.core.deps import get_current_user


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, org_user):
    org, user = org_user
    r = await client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": "password123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "user" in data
    assert data["user"]["email"] == "test@test.com"
    assert data["user"]["org_id"] == str(org.id)
    assert "csrf_token" in data
    assert "access_token" in r.cookies or "Set-Cookie" in r.headers


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, org_user):
    r = await client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": "wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_unauthorized(client: AsyncClient):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_after_login(client: AsyncClient, org_user):
    await client.post(
        "/api/auth/login",
        json={"email": "test@test.com", "password": "password123"},
    )
    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "test@test.com"
