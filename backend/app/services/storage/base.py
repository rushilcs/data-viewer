"""Storage backend interface: presigned put/get and head. Implementations: local (dev disk) or S3."""
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract storage: presigned URLs for upload/download and head for integrity checks."""

    @abstractmethod
    def create_presigned_put(
        self,
        storage_key: str,
        content_type: str,
        byte_size: int,
        expires_s: int,
        **kwargs,
    ) -> str:
        """Return a URL that allows uploading object to storage_key (PUT). kwargs may include asset_id, org_id, dataset_id for local backend."""
        ...

    @abstractmethod
    def create_presigned_get(
        self,
        storage_key: str,
        expires_s: int,
        disposition_filename: str | None = None,
        response_content_type: str | None = None,
        **kwargs,
    ) -> str:
        """Return a URL that allows downloading the object. kwargs may include asset_id, org_id for local backend."""
        ...

    @abstractmethod
    def head_object(self, storage_key: str) -> dict:
        """Return metadata: content_length (int), content_type (str). Raise FileNotFoundError if missing."""
        ...
