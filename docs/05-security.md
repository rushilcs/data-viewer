# FILE: docs/05-security.md

# Security Checklist (v1)

## 1) Authentication
- Password-based auth (Argon2)
- Rate limiting on login (config: `login_rate_limit_per_minute`); ingest endpoints also rate-limited
- Session cookies: HttpOnly, **Secure** (config: `cookie_secure=true` in prod), **SameSite** (config: `cookie_samesite=lax` or `strict`)
- CSRF: double-submit cookie (`csrf_token` non-HttpOnly + `X-CSRF-Token` header) on all state-changing endpoints

## 2) Authorization (Multi-tenant)
- Every DB query scoped by org_id
- No “fetch by id then check org” patterns that can be bypassed; enforce scoping in queries
- Do not return different errors that allow resource enumeration across orgs

## 3) Object Storage
- Private bucket
- Server-minted signed URLs only after auth check
- Short TTL (60–300s)
- Restrict methods: PUT for upload URLs, GET for download URLs
- Validate content-type and size on ingest; optionally verify sha256 on publish

## 4) Upload Validation
- Strict content-type allowlist and per-kind max size (config)
- Sanitized filenames (no path separators; server-generated storage keys: `org_id/dataset_id/{uuid}_{safe_filename}`)
- Optional antivirus hook: `app.services.av_scan.scan_upload` (stub; set `enable_av_scan=true` when integrated)

## 5) Web Security
- **Headers:** X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Content-Security-Policy (default-src 'self'; frame-ancestors 'none'), Permissions-Policy
- CORS: strict allowlist via `cors_origins` (prod: only frontend origin(s))
- No secrets in frontend env
- Sanitization of any rendered text (prompts, metadata) to prevent XSS

## 6) Logging & Auditing
- Log publish events, dataset access, signed URL minting
- **Secrets hygiene:** Audit event_data is passed through `redact_for_log()` (no JWTs, cookies, passwords, invite tokens). Never log Cookie or Authorization headers in app logs.

## 7) Operational
- Separate dev/staging/prod AWS accounts or at least separate buckets/DBs/IAM
- Least-privilege IAM roles
- DB backups and rotation