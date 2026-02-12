# FILE: docs/01-architecture.md

# Architecture

## 1) High-Level Components
- Web Frontend (Next.js): UI, viewer modules, calls API, never stores long-lived secrets
- API Backend (FastAPI): auth, authorization, dataset/item APIs, signed URL minting, ingestion validation
- Database (Postgres/RDS): users, orgs, datasets, items, assets, annotations, access logs
- Object Storage (S3): private bucket(s) for assets, thumbnails, derived artifacts
- Background Jobs (optional v1, likely v1.1): thumbnail generation, video poster frames, transcript indexing

## 2) Primary Flows

### A) View Flow (Client)
1) User logs in
2) Frontend requests datasets: GET /api/datasets
3) User opens dataset: GET /api/datasets/{dataset_id}
4) Frontend paginates items: GET /api/datasets/{dataset_id}/items?type=...&tag=...&cursor=...
5) User opens item: GET /api/items/{item_id}
6) For each asset, frontend requests signed URL: POST /api/assets/{asset_id}/signed-url
7) Frontend loads media via signed URL directly from S3 (short TTL)

### B) Ingestion Flow (Internal Publisher / SDK)
1) Create draft dataset upload session: POST /api/ingest/datasets
2) Request signed upload URLs: POST /api/ingest/assets:batch
3) Upload binaries to S3 (PUT to signed URLs)
4) Submit manifest: POST /api/ingest/datasets/{dataset_id}/publish
5) Backend validates:
   - schema per item.type
   - referenced asset keys exist
   - org ownership matches
6) Backend marks dataset “published” atomically

## 3) Multi-Tenancy
- All core tables include org_id
- All queries are scoped by org_id derived from authenticated identity + permissions
- Access policy:
  - users belong to orgs
  - datasets belong to orgs
  - optional dataset ACLs (per-user or group) can be added; v1 can start with org-wide access

## 4) Asset Security
- S3 bucket private
- Assets stored with non-guessable keys (uuid prefixes)
- API mints signed GET URLs with:
  - short TTL (e.g., 60–300 seconds)
  - content-disposition safe defaults
  - cache-control private/no-store for sensitive content
- Optional: signed URL minting also checks dataset published + user permission

## 5) Scalability Notes (v1)
- Server-side pagination for item lists
- DB indexes on (org_id, dataset_id, created_at), (org_id, dataset_id, type), tags if used
- Heavy media served directly from S3 via signed URLs (API not a bandwidth bottleneck)