"""Storage backend factory: local (dev disk) or S3. S3 backend is loaded only when STORAGE_BACKEND=s3 (no boto3 in local)."""
from app.core.config import get_settings
from app.services.storage.base import StorageBackend
from app.services.storage.local import LocalStorage


def get_storage() -> StorageBackend:
    """Return the configured storage backend. Avoids importing boto3 when backend is local."""
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.services.storage.s3 import S3Storage
        return S3Storage()
    return LocalStorage()
