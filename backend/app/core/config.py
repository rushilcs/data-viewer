"""Application settings."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """App config from env."""

    app_name: str = "Modular Client Dataset Viewer"
    debug: bool = False
    # Structured logging: set LOG_JSON=1 for one-JSON-object-per-line (CloudWatch, etc.)
    log_json: bool = False
    # Metrics: require admin auth (True) or set metrics_secret and send X-Metrics-Secret header
    metrics_require_admin: bool = True
    metrics_secret: str | None = None  # if set, /metrics can use this header instead of admin

    # DB (host 5433 to avoid conflict with local Postgres on 5432).
    # For RDS/prod, set DATABASE_URL with sslmode=require (e.g. postgresql+asyncpg://...?sslmode=require).
    database_url: str = "postgresql+asyncpg://viewer:viewer@localhost:5433/viewer"

    # Auth
    secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cookie_name: str = "access_token"
    csrf_cookie_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    # Cookie security: prod should set cookie_secure=true, cookie_samesite=strict or lax
    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # lax | strict

    # CORS (strict allowlist; local dev uses multiple origins)
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003,http://localhost:3004,http://localhost:3005,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3002,http://127.0.0.1:3003,http://127.0.0.1:3004,http://127.0.0.1:3005"

    # Storage: local (dev disk) or s3 (AWS). Default local so no AWS required.
    storage_backend: str = "local"  # local | s3
    # Dev assets (local disk)
    dev_assets_dir: str = "./dev_assets"
    signed_url_ttl_seconds: int = 300
    # In-memory cache for signed URLs (per asset+user); 0 = disabled. Short TTL to avoid stale URLs.
    signed_url_cache_ttl_seconds: int = 0  # e.g. 60 in prod to reduce backend load

    # Upload (ingest) - signed PUT URL TTL
    upload_token_ttl_seconds: int = 300  # 5 min

    # S3 (only used when storage_backend=s3)
    s3_bucket: str | None = None
    aws_region: str = "us-east-1"
    # Presigned GET TTL for S3 (seconds)
    s3_signed_url_ttl_seconds: int = 300

    # Secrets Manager (optional; overlay DATABASE_URL, secret_key, etc. at startup)
    aws_secrets_arn: str | None = None

    # Upload validation (docs/05-security.md)
    content_type_allowlist: str = "image/png,image/jpeg,image/webp,video/mp4,audio/mpeg,audio/wav,audio/webm,text/vtt,application/json"
    enable_av_scan: bool = False  # Stub in app; set True in prod when AV integrated
    max_byte_size_image_mb: int = 50
    max_byte_size_video_mb: int = 500
    max_byte_size_audio_mb: int = 100
    max_byte_size_other_mb: int = 10

    # Feature flags (ops: disable ingestion without redeploy)
    ingest_enabled: bool = True  # set False to return 503 on publish/append (runbook: disable ingestion)

    # Rate limit
    login_rate_limit_per_minute: int = 10
    ingest_rate_limit_per_minute: int = 60  # per user/identifier; stricter in prod

    # Open signup: org for new users when they have no pending shares (optional UUID; else first org)
    default_org_id: str | None = None

    # Search: ilike (simple) or fts (full-text via tsvector). Default ilike for local.
    search_backend: str = "ilike"  # ilike | fts

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
