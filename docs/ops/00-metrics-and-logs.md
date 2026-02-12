# Metrics and logs (observability)

## Logs

- **Structured JSON** (when `LOG_JSON=1`): one JSON object per line. Fields include `event`, `request_id`, `method`, `path`, `status_code`, `latency_ms`, and optionally `org_id`/`user_id` (redacted; no PII). Use for CloudWatch Logs Insights and log aggregation.
- **Local default**: human-readable logs; set `LOG_JSON=1` to test JSON locally.
- **Request ID**: Every response includes `X-Request-ID`. Use it to trace a request in logs.

## Metrics endpoint (`/metrics`)

Prometheus-format metrics: request count by route/status, latency histogram, publish success/failure, signed-url mint count.

### Guarding in production

- **Option 1 — Admin auth**  
  Set `METRICS_REQUIRE_ADMIN=1` (default). Only authenticated **admin** users can access `GET /metrics` (cookie/session).
- **Option 2 — Secret header**  
  Set `METRICS_SECRET=<secret>`. Requests must include header `X-Metrics-Secret: <secret>`. Use for Prometheus scraping from a trusted network (e.g. same VPC); do not expose the endpoint publicly.
- **Local**: Set `METRICS_REQUIRE_ADMIN=0` and leave `METRICS_SECRET` unset to allow unauthenticated `/metrics` for development.

Recommendation: in prod, use **Option 2** for a scraper in the same VPC and keep the ALB/listener from exposing `/metrics` to the internet, or use **Option 1** and scrape as an admin (e.g. with a dedicated service account).
