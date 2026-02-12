"""
Python client for the ingestion API: login, create_dataset, upload_assets, publish.
Supports robust retries with exponential backoff; optional S3 multipart for large files (feature-flagged).
"""
import mimetypes
import os
import time
from pathlib import Path
from uuid import UUID

import httpx

# Use S3 multipart for files above this size (bytes) when upload_url is S3. Set USE_S3_MULTIPART=1 to enable.
S3_MULTIPART_THRESHOLD_BYTES = 100 * 1024 * 1024  # 100 MB
USE_S3_MULTIPART = os.environ.get("USE_S3_MULTIPART", "").lower() in ("1", "true", "yes")


class DatasetClient:
    """Client for dataset ingestion (draft, upload assets, publish)."""

    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self._csrf_token: str | None = None
        self._session: httpx.Client | None = None

    def _get_session(self) -> httpx.Client:
        if self._session is None:
            self._session = httpx.Client(
                base_url=self.base_url,
                timeout=60.0,
                follow_redirects=True,
            )
        return self._session

    def login(self) -> dict:
        """Login and store cookies + CSRF token."""
        session = self._get_session()
        r = session.post(
            "/api/auth/login",
            json={"email": self.email, "password": self.password},
        )
        r.raise_for_status()
        for name, value in r.cookies.items():
            session.cookies.set(name, value)
        data = r.json()
        self._csrf_token = data.get("csrf_token")
        return data

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._csrf_token:
            h["X-CSRF-Token"] = self._csrf_token
        return h

    def create_dataset(
        self,
        name: str,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Create a draft dataset. Returns { dataset_id, status }."""
        session = self._get_session()
        body = {"name": name}
        if description is not None:
            body["description"] = description
        if tags is not None:
            body["tags"] = tags
        r = session.post(
            "/api/ingest/datasets",
            json=body,
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    def upload_assets(
        self,
        dataset_id: str | UUID,
        local_file_paths: list[str | Path],
        kind_hint: str | None = None,
    ) -> dict[str, str]:
        """
        Request batch upload URLs, then PUT each file. Returns mapping filename -> asset_id (str).
        kind_hint: "image" | "video" | "audio" | "other" applied to all if set; else guessed from extension.
        """
        dataset_id = str(dataset_id)
        session = self._get_session()
        files_spec = []
        path_list = [Path(p) for p in local_file_paths]
        for p in path_list:
            if not p.exists():
                raise FileNotFoundError(p)
            size = p.stat().st_size
            content_type, _ = mimetypes.guess_type(str(p)) or ("application/octet-stream", None)
            kind = kind_hint or _guess_kind(content_type, p.suffix)
            files_spec.append({
                "filename": p.name,
                "kind": kind,
                "content_type": content_type,
                "byte_size": size,
            })
        r = session.post(
            "/api/ingest/assets:batch",
            json={"dataset_id": dataset_id, "files": files_spec},
            headers=self._headers(),
        )
        r.raise_for_status()
        batch = r.json()
        result = {}
        for i, spec in enumerate(batch):
            local_path = path_list[i]
            asset_id = spec["asset_id"]
            upload_url = spec["upload_url"]
            size = path_list[i].stat().st_size
            content_type = files_spec[i]["content_type"]
            self._upload_one(upload_url, local_path, size=size, content_type=content_type)
            result[local_path.name] = str(asset_id)
        return result

    def _upload_one(
        self,
        upload_url: str,
        path: Path,
        size: int | None = None,
        content_type: str = "application/octet-stream",
    ) -> None:
        size = size or path.stat().st_size
        if USE_S3_MULTIPART and size >= S3_MULTIPART_THRESHOLD_BYTES and "amazonaws.com" in upload_url:
            self._put_file_s3_multipart(upload_url, path, size, content_type)
        else:
            self._put_file_with_retry(upload_url, path, size=size, content_type=content_type)

    def _put_file_s3_multipart(
        self,
        upload_url: str,
        path: Path,
        size: int,
        content_type: str,
    ) -> None:
        """S3 multipart upload for large files. Requires backend to support multipart (init/part/complete). Stub: fallback to single PUT with retry."""
        # When backend exposes multipart init + part URLs + complete, implement here (boto3 or presigned part URLs).
        self._put_file_with_retry(upload_url, path, size=size, content_type=content_type)

    def _put_file_with_retry(
        self,
        upload_url: str,
        path: Path,
        size: int | None = None,
        content_type: str = "application/octet-stream",
        max_retries: int = 5,
    ) -> None:
        size = size or path.stat().st_size
        body = path.read_bytes()
        if len(body) != size:
            raise ValueError(f"File size changed: expected {size}, got {len(body)}")
        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                r = self._get_session().put(
                    upload_url,
                    content=body,
                    headers={"Content-Type": content_type},
                )
                r.raise_for_status()
                return
            except httpx.HTTPError as e:
                last_err = e
                if attempt == max_retries - 1:
                    raise
                backoff = (2**attempt) + (time.time() % 1)  # exponential backoff + jitter
                time.sleep(backoff)
        if last_err:
            raise last_err

    def publish(self, dataset_id: str | UUID, manifest_dict: dict) -> dict:
        """Publish dataset with manifest. Returns { dataset_id, status, item_count }."""
        dataset_id = str(dataset_id)
        session = self._get_session()
        r = session.post(
            f"/api/ingest/datasets/{dataset_id}/publish",
            json={"manifest": manifest_dict},
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self) -> "DatasetClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _guess_kind(content_type: str, suffix: str) -> str:
    ct = (content_type or "").lower()
    if ct.startswith("image/") or suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return "image"
    if ct.startswith("video/") or suffix.lower() in (".mp4", ".webm", ".mov"):
        return "video"
    if ct.startswith("audio/") or suffix.lower() in (".mp3", ".wav", ".webm", ".m4a"):
        return "audio"
    return "other"
