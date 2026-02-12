# Modular Client Dataset Viewer

**Milestone 1:** Read-only viewer with auth, org-scoped datasets/items, signed asset URLs.  
**Milestone 2:** Ingestion (draft → upload assets → publish), Python SDK/CLI, manifest validation, atomic publish.  
**Milestone 3:** Filtering/search for items, item-type-counts, normalized timeline/captions in item detail, demo data generator, rich viewers (zoom, timeline seek, caption highlight).  
**Milestone 4:** Strict validation, multi-tenant isolation, signed URL safety, E2E tests, frontend error handling, single-command local boot.

## Architecture (brief)

- **Frontend (Next.js):** UI, viewer registry per item type, calls API with cookie auth; no long-lived secrets.
- **Backend (FastAPI):** Auth (JWT in cookie), org-scoped datasets/items/assets, signed URL minting (HMAC + expiry), ingestion (draft → upload → publish). All lookups scoped by `org_id`.
- **Database (Postgres):** Organizations, users, datasets, items, assets, annotations. Local dev uses `docker-compose`; assets on local disk (`dev_assets/`).
- **SDK/CLI:** Python `dataset-uploader` for create, upload, publish with manifest.

See `docs/01-architecture.md` for flows and multi-tenancy.

## How to run locally

### Option A — Single command (recommended)

From repo root (requires Docker, Python venv, Node):

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

This starts Postgres, runs migrations and demo data, then starts backend (background) and frontend (foreground). Open http://localhost:3000.

### Option B — Manual (three terminals)

**1. Postgres**
```bash
cd backend && make up
# or: docker-compose up -d
```

**2. Backend**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
make upgrade
make seed
make run
```

**3. Frontend**
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Log in as:
- **admin@verita.com** / **admin123** (Verita)
- **admin@beta.com** / **admin123** (Beta Inc)

---

## Ingestion (Milestone 2)

Only users with role **admin** or **publisher** can create draft datasets and publish.

### 1. Create draft dataset
```bash
cd sdk
pip install -e .
dataset-uploader --email admin@verita.com --password admin123 create --name "My Dataset"
# Copy the returned dataset_id.
```

### 2. Upload assets
```bash
dataset-uploader --email admin@verita.com --password admin123 upload \
  --dataset-id <dataset_id> \
  left.png right.png
# Output maps filename -> asset_id. Use these UUIDs in your manifest.
```

### 3. Publish with manifest
Edit `example_manifest.json` (or your own): replace placeholders with the asset UUIDs from step 2. Then:

```bash
dataset-uploader --email admin@verita.com --password admin123 publish \
  --dataset-id <dataset_id> \
  --manifest example_manifest.json
```

### Example manifest shape
See `example_manifest.json` in the repo root. Each item has:
- `type`: one of `image_pair_compare`, `image_ranked_gallery`, `video_with_timeline`, `audio_with_captions`
- `title`, `summary` (optional)
- `payload`: type-specific (see docs/03-item-schemas.md)
- `annotations`: optional list of `{ "schema": "timeline_v1"|"captions_v1", "data": {...} }`

### Python SDK usage
```python
from dataset_uploader import DatasetClient

with DatasetClient("http://localhost:8000", "admin@verita.com", "admin123") as client:
    client.login()
    out = client.create_dataset("My Dataset", description="Optional")
    dataset_id = out["dataset_id"]
    mapping = client.upload_assets(dataset_id, ["left.png", "right.png"])
    # Build manifest with mapping["left.png"], mapping["right.png"] as asset_ids
    client.publish(dataset_id, {"items": [...]})
```

---

## Makefile (backend)

```bash
cd backend
make up       # docker-compose up -d (Postgres only)
make run      # uvicorn
make upgrade  # alembic upgrade head
make seed     # python scripts/seed_dev.py
make demo     # upgrade + seed + generate_demo_data.py (3 datasets per org, ~50 items each)
make load-test # generate 10k-item dataset and measure list/item-detail latency (after seed + upgrade)
make test     # pytest (use PYTHONPATH=. if needed)
make reset    # drop DB, recreate schema, seed + demo (clean local state)
```

**Scalability (local unchanged):**
- Items list is **cursor-paginated** (keyset on `created_at`, `id`); use `cursor` and `limit` query params.
- **Search:** `SEARCH_BACKEND=ilike` (default) or `fts`; set `fts` and run migration 004 for full-text search on items.
- **Signed URLs:** Frontend caches with TTL and dedupes in-flight requests; backend can set `signed_url_cache_ttl_seconds` (e.g. 60) for a short per-asset+user cache.
- **SDK:** Upload uses exponential-backoff retries; optional `USE_S3_MULTIPART=1` for future S3 multipart (stub).

---

## How to generate demo data

After Postgres and migrations are up:

```bash
cd backend
make demo
```

This runs `upgrade`, `seed`, then `generate_demo_data.py --seed 42 --items-per-dataset 50`, creating 3 published datasets per org with mixed item types (image pair, gallery, video, audio) and sample assets.

---

## Running locally (default)

- **Storage:** `STORAGE_BACKEND=local` (default). Assets are stored on disk (`backend/dev_assets/`). Upload and download use backend URLs with HMAC tokens; no AWS required.
- **Database:** Local Postgres (e.g. `docker-compose`). No SSL required.
- **Secrets:** Use `.env` (e.g. `DATABASE_URL`, `secret_key`). Do not set `AWS_SECRETS_ARN`.

## Enabling AWS mode (optional)

To use S3 for assets and optional RDS + Secrets Manager:

1. **Environment variables**
   - `STORAGE_BACKEND=s3`
   - `S3_BUCKET=<your-bucket>`
   - `AWS_REGION` (default `us-east-1`)
   - `S3_SIGNED_URL_TTL_SECONDS` (default 300) — TTL for presigned GET URLs
   - Optional: `AWS_SECRETS_ARN` — Secrets Manager secret ARN; at startup the app fetches the secret JSON and overlays `DATABASE_URL`, `secret_key`, etc. (never logged).
   - For RDS: set `DATABASE_URL` with `?sslmode=require` (or via the secret).

2. **Dependencies:** `pip install -r requirements.txt` (includes `boto3` for S3 and Secrets Manager).

3. **Behavior**
   - **Ingestion:** `POST /api/ingest/assets:batch` returns **presigned PUT URLs** to S3; the client uploads directly to S3. `PUT /api/ingest/assets/{id}/upload` is only used in local mode.
   - **Viewing:** `POST /api/assets/{id}/signed-url` returns a **presigned GET URL** to S3 (short TTL). There is no stream endpoint for S3; the client uses the returned URL directly.
   - **Publish:** At publish (and append), the backend checks that each referenced asset exists in storage (head) and that size (and content type where available) match; otherwise validation fails.

4. **Local mode unchanged:** If you do not set `STORAGE_BACKEND=s3` or `AWS_SECRETS_ARN`, the app runs exactly as before with no boto3 usage for storage (boto3 is only imported when S3 or Secrets Manager is configured).

- **Deployment:** For production-style AWS (ECS Fargate, ALB, RDS, S3), see **`docs/deploy/aws-ecs.md`**. Local dev does not use Docker for the backend; containerization is additive.

## Known limitations (local use)

- **Storage (local):** Assets on disk only unless AWS mode is enabled (see above).
- **No background workers:** No thumbnail generation, indexing, or async jobs.
- **Auth:** Single org per user; no fine-grained ACLs beyond org scope.
- **Tests:** Backend tests require Postgres (e.g. `viewer_test` DB). Run with `cd backend && make test` (or `PYTHONPATH=. pytest tests/ -v`).

---

## Acceptance (M1–M4)

- **M1:** Login, list/detail datasets, view items, signed asset URLs, viewer registry.
- **M2:** Create draft → upload assets (SDK) → publish with manifest; invalid manifest → 422, nothing persisted; assets linked to items; upload token expiry and wrong asset_id rejected; draft datasets visible to admin/publisher; "Publish Dataset (via SDK)" on draft dataset page.
- **M3:** Filter/search items, item-type-counts, timeline/captions in item detail, demo data, rich viewers.
- **M4:** Strict Pydantic validation (extra=forbid), manifest errors with path/type/message; no partial publish; state guards (409 for publish twice, upload to published); multi-tenant isolation tests (404 cross-org); signed URL HMAC/expiry tests; E2E test (login → create → upload → publish → list → item → signed URL → stream); frontend 401→login, 404→"Not found or not authorized", signed URL retry once; single-command boot (`scripts/dev.sh`), `make reset`.

## Tech stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Alembic, Postgres, JWT (HttpOnly cookie), CSRF, Argon2, ingest endpoints, item type registry (Pydantic, extra=forbid).
- **Frontend:** Next.js (App Router), TypeScript, Tailwind, viewer registry.
- **SDK:** Python (httpx), CLI `dataset-uploader` (create, upload, publish).
