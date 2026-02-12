"""S3 storage backend: presigned PUT/GET and head. Imported only when STORAGE_BACKEND=s3 (avoids boto3 in local mode)."""
from __future__ import annotations

from urllib.parse import quote

from app.core.config import get_settings
from app.services.storage.base import StorageBackend

settings = get_settings()


def _get_client():
    import boto3
    return boto3.client("s3", region_name=settings.aws_region)


class S3Storage(StorageBackend):
    """S3 backend: presigned PUT/GET via boto3; head_object via HeadObject."""

    def __init__(self) -> None:
        if not settings.s3_bucket:
            raise ValueError("S3 storage requires s3_bucket to be set")
        self._bucket = settings.s3_bucket
        self._client = _get_client()
        self._ttl = getattr(settings, "s3_signed_url_ttl_seconds", 300)

    def create_presigned_put(
        self,
        storage_key: str,
        content_type: str,
        byte_size: int,
        expires_s: int,
        **kwargs,
    ) -> str:
        url = self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": storage_key,
                "ContentType": content_type,
                "ContentLength": byte_size,
            },
            ExpiresIn=expires_s,
        )
        return url

    def create_presigned_get(
        self,
        storage_key: str,
        expires_s: int,
        disposition_filename: str | None = None,
        response_content_type: str | None = None,
        **kwargs,
    ) -> str:
        params = {"Bucket": self._bucket, "Key": storage_key}
        if response_content_type:
            params["ResponseContentType"] = response_content_type
        if disposition_filename:
            # RFC 5987 style for filename with special chars
            safe = quote(disposition_filename)
            params["ResponseContentDisposition"] = f"inline; filename*=UTF-8''{safe}"
        url = self._client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_s,
        )
        return url

    def head_object(self, storage_key: str) -> dict:
        try:
            resp = self._client.head_object(Bucket=self._bucket, Key=storage_key)
        except Exception as e:
            resp = getattr(e, "response", None)
            code = (resp.get("Error", {}).get("Code") if isinstance(resp, dict) else None)
            if code in ("404", "NoSuchKey"):
                raise FileNotFoundError(f"Object not found: {storage_key}") from e
            raise
        return {
            "content_length": resp.get("ContentLength") or 0,
            "content_type": resp.get("ContentType"),
        }
