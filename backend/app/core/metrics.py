"""Prometheus metrics: request count by route/status, latency, publish, signed-url mint."""
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total requests",
    ["method", "path", "status_class"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
PUBLISH_TOTAL = Counter(
    "ingest_publish_total",
    "Publish attempts",
    ["result"],  # success | failure
)
SIGNED_URL_MINT_TOTAL = Counter(
    "assets_signed_url_mint_total",
    "Signed URL mints",
)


def _status_class(status: int) -> str:
    if status < 200:
        return "1xx"
    if status < 300:
        return "2xx"
    if status < 400:
        return "3xx"
    if status < 500:
        return "4xx"
    return "5xx"


def record_request(method: str, path: str, status_code: int, latency_seconds: float) -> None:
    path = path or "/"
    # Normalize path to avoid high cardinality (e.g. /api/items/123 -> /api/items/{id})
    if path.startswith("/api/items/") and len(path) > len("/api/items/"):
        path = "/api/items/{id}"
    elif path.startswith("/api/datasets/") and "/items" not in path and len(path) > len("/api/datasets/"):
        path = "/api/datasets/{id}"
    elif path.startswith("/api/assets/") and len(path) > len("/api/assets/"):
        path = "/api/assets/{id}"
    sc = _status_class(status_code)
    REQUEST_COUNT.labels(method=method, path=path, status_class=sc).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(latency_seconds)


def record_publish_success() -> None:
    PUBLISH_TOTAL.labels(result="success").inc()


def record_publish_failure() -> None:
    PUBLISH_TOTAL.labels(result="failure").inc()


def record_signed_url_mint() -> None:
    SIGNED_URL_MINT_TOTAL.inc()


def get_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
