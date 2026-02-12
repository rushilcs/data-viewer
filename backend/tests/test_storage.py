"""Storage backends: local behaviour and S3 path with mocks (no real AWS)."""
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.services.storage import get_storage
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorage


def test_sanitize_storage_filename():
    from app.services.upload_validation import sanitize_storage_filename
    assert sanitize_storage_filename("a/b/c.png") == "c.png"
    assert sanitize_storage_filename("normal.png") == "normal.png"
    assert sanitize_storage_filename("weird name!.png") == "weird_name_.png"
    assert sanitize_storage_filename("") == ""
    assert sanitize_storage_filename(None) == ""


def test_get_storage_returns_local_by_default(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    # Clear lru_cache so get_settings picks up env
    get_settings.cache_clear()
    try:
        backend = get_storage()
        assert isinstance(backend, LocalStorage)
    finally:
        get_settings.cache_clear()


def test_local_storage_presigned_put_url():
    settings = get_settings()
    root = Path(settings.dev_assets_dir)
    backend = LocalStorage()
    asset_id = uuid4()
    org_id = uuid4()
    dataset_id = uuid4()
    url = backend.create_presigned_put(
        "org/ds/key",
        "image/png",
        100,
        300,
        asset_id=asset_id,
        org_id=org_id,
        dataset_id=dataset_id,
        base_url="http://test",
    )
    assert f"/api/ingest/assets/{asset_id}/upload" in url
    assert "token=" in url
    assert "http://test" in url


def test_local_storage_presigned_get_url():
    backend = LocalStorage()
    url = backend.create_presigned_get(
        "org/ds/key",
        300,
        base_url="http://test",
        asset_id=uuid4(),
        org_id=uuid4(),
    )
    assert "/api/assets/" in url
    assert "/stream" in url
    assert "token=" in url


def test_local_storage_head_object_missing():
    backend = LocalStorage()
    with pytest.raises(FileNotFoundError, match="not found"):
        backend.head_object("nonexistent/or/path")


def test_local_storage_head_object_exists(tmp_path):
    backend = LocalStorage()
    backend._root = tmp_path
    (tmp_path / "a").mkdir(parents=True)
    (tmp_path / "a" / "b.bin").write_bytes(b"x" * 42)
    meta = backend.head_object("a/b.bin")
    assert meta["content_length"] == 42
    assert meta["content_type"] is None


def test_s3_storage_requires_bucket(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="s3_bucket"):
            from app.services.storage.s3 import S3Storage
            S3Storage()
    finally:
        get_settings.cache_clear()


def test_s3_presigned_put_get_mocked():
    """S3 path: presigned put/get via boto3 stub (no real AWS)."""
    from unittest.mock import MagicMock, patch

    with patch("app.services.storage.s3._get_client") as m_get_client:
        client = MagicMock()
        def _presigned(op, **kw):
            params = kw.get("Params", {})
            return f"https://mock-s3/{op}?key={params.get('Key', '')}"
        client.generate_presigned_url.side_effect = _presigned
        m_get_client.return_value = client

        with patch("app.services.storage.s3.settings") as m_settings:
            m_settings.s3_bucket = "test-bucket"
            m_settings.aws_region = "us-east-1"
            m_settings.s3_signed_url_ttl_seconds = 300
            from app.services.storage.s3 import S3Storage
            storage = S3Storage()
            storage._client = client

        put_url = storage.create_presigned_put("org/ds/key.png", "image/png", 100, 300)
        assert "https://mock-s3" in put_url and "org/ds/key.png" in put_url
        get_url = storage.create_presigned_get("org/ds/key.png", 60)
        assert "https://mock-s3" in get_url


def test_s3_head_object_not_found_mocked():
    """S3 head_object raises FileNotFoundError when object does not exist."""
    from unittest.mock import MagicMock, patch

    class Fake404(Exception):
        response = {"Error": {"Code": "404"}}

    with patch("app.services.storage.s3._get_client") as m_get_client:
        client = MagicMock()
        client.head_object.side_effect = Fake404()
        m_get_client.return_value = client

        with patch("app.services.storage.s3.settings") as m_settings:
            m_settings.s3_bucket = "test-bucket"
            m_settings.aws_region = "us-east-1"
            m_settings.s3_signed_url_ttl_seconds = 300
            from app.services.storage.s3 import S3Storage
            storage = S3Storage()
            storage._client = client

        with pytest.raises(FileNotFoundError, match="not found"):
            storage.head_object("missing/key")