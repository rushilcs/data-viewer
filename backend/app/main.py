"""FastAPI app: CORS, security headers, routers."""
import os

# Optional: overlay env from AWS Secrets Manager (prod). Only when ARN set; never log secrets.
_aws_secrets_arn = os.environ.get("AWS_SECRETS_ARN")
if _aws_secrets_arn:
    try:
        import json
        import boto3
        _sm = boto3.client("secretsmanager")
        _r = _sm.get_secret_value(SecretId=_aws_secrets_arn)
        _data = json.loads(_r["SecretString"]) if _r.get("SecretString") else {}
        for _k, _v in (_data or {}).items():
            if isinstance(_v, str):
                os.environ[_k] = _v
    except Exception:
        # Log exception type only, never secret content
        import logging
        logging.getLogger(__name__).exception("Failed to load AWS Secrets Manager secret")

import logging
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.core.config import get_settings
from app.core.request_logging import RequestLoggingMiddleware
from app.core.deps import require_metrics_access
from app.core.metrics import get_metrics
from app.db import get_db
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.datasets import router as datasets_router
from app.api.items import router as items_router
from app.api.assets import router as assets_router
from app.api.ingest import router as ingest_router

settings = get_settings()
if settings.log_json:
    for h in logging.getLogger("app.request").handlers[:]:
        logging.getLogger("app.request").removeHandler(h)
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("app.request").addHandler(h)
    logging.getLogger("app.request").setLevel(logging.INFO)

app = FastAPI(title=settings.app_name)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", settings.csrf_header_name],
)

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none';"
    response.headers["Permissions-Policy"] = "accelerometer=(), camera=(), geolocation=(), microphone=(), payment=(), usb=()"
    return response

app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(items_router, prefix="/api")
app.include_router(assets_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/healthz")
async def healthz():
    """Liveness: no auth, no DB. Used by ALB/ECS."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness: light DB check. Used by ALB/ECS to avoid routing to unhealthy tasks."""
    from sqlalchemy import text
    from app.db.session import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "database unreachable"},
        )


@app.get("/metrics", response_class=Response)
async def metrics(_: None = Depends(require_metrics_access)):
    """Prometheus metrics. In prod guard via METRICS_REQUIRE_ADMIN=1 (admin auth) or METRICS_SECRET + X-Metrics-Secret header."""
    body, content_type = get_metrics()
    return Response(content=body, media_type=content_type)
