"""Local (dev disk) storage: backend upload/stream URLs with HMAC tokens; head via file stat."""
from pathlib import Path
from uuid import UUID

from app.core.config import get_settings
from app.core.security import create_upload_token, create_asset_stream_token
from app.services.storage.base import StorageBackend

settings = get_settings()


class LocalStorage(StorageBackend):
    """Dev disk storage: presigned put/get are backend URLs with HMAC tokens; head checks file path."""

    def __init__(self) -> None:
        self._root = Path(settings.dev_assets_dir)

    def create_presigned_put(
        self,
        storage_key: str,
        content_type: str,
        byte_size: int,
        expires_s: int,
        **kwargs,
    ) -> str:
        asset_id: UUID = kwargs["asset_id"]
        org_id: UUID = kwargs["org_id"]
        dataset_id: UUID = kwargs["dataset_id"]
        base_url: str = kwargs["base_url"]
        token = create_upload_token(asset_id, org_id, dataset_id, byte_size)
        return f"{base_url.rstrip('/')}/api/ingest/assets/{asset_id}/upload?token={token}"

    def create_presigned_get(
        self,
        storage_key: str,
        expires_s: int,
        disposition_filename: str | None = None,
        response_content_type: str | None = None,
        **kwargs,
    ) -> str:
        asset_id: UUID = kwargs["asset_id"]
        org_id: UUID = kwargs["org_id"]
        base_url: str = kwargs["base_url"]
        token = create_asset_stream_token(asset_id, org_id)
        return f"{base_url.rstrip('/')}/api/assets/{asset_id}/stream?token={token}"

    def head_object(self, storage_key: str) -> dict:
        path = self._root / storage_key
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Object not found: {storage_key}")
        size = path.stat().st_size
        # Local files don't store content_type; caller can compare with Asset.content_type
        return {"content_length": size, "content_type": None}
