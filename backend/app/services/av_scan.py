"""Antivirus scanning hook for uploads. Stub implementation; integrate with ClamAV/S3 scan/etc. in prod."""
from __future__ import annotations


def scan_upload(content: bytes, content_type: str, storage_key: str) -> bool:
    """Return True if content is considered safe, False if malware detected.
    Stub: always returns True. In prod, wire to ClamAV daemon, S3 Object Lambda, or similar.
    """
    _ = content_type, storage_key
    if not content:
        return True
    # Stub: no-op. Replace with actual scan, e.g.:
    # return clamav_scan_bytes(content)
    return True
