# FILE: docs/04-api-spec.md

# API Spec (v1)

Base: /api
Auth: session cookie or JWT (decide in implementation; must support browser use)

## 1) Auth
POST /api/auth/login
- body: { email, password }
- returns: session/JWT

POST /api/auth/signup (open)
- body: { email, password }
- creates user in org: org from first pending_dataset_share for this email, else default_org_id or first org; role=viewer
- applies any pending_dataset_share rows for (org_id, email) as dataset_access, then deletes pending rows
- returns session (same as login)

POST /api/auth/logout

GET /api/auth/me
- returns: user profile + org

## 2) Datasets
GET /api/datasets
- returns: datasets visible to user (admin/publisher: all in org; viewer: only those in dataset_access)

GET /api/datasets/{dataset_id}
- returns: dataset metadata (must enforce org/ACL)

GET /api/datasets/{dataset_id}/items
- query: type?, tag?, q?, created_after?, created_before?, limit? (default 25, max 100), cursor?
- returns: paginated list of item summaries (items, next_cursor, has_more)
- Search (q): ILIKE over items.title, items.summary, items.payload::text (local extension)
- tag: filters by dataset tags (if item has no tags, dataset tags only) (local extension)

GET /api/datasets/{dataset_id}/item-type-counts (local extension)
- returns: { counts: { [type]: number }, total: number }
- org-scoped, fast

## 3) Items
GET /api/items/{item_id}
- returns: item detail (payload + referenced assets + annotations)
- backend should return asset metadata and annotation blobs needed to render
- Local extension: derived convenience for viewers:
  - timeline_events: for video_with_timeline, normalized list { t_start, t_end?, label, metadata?, track? }
  - caption_segments: for audio_with_captions, normalized list { t_start, t_end?, text }

## 4) Assets (view)
POST /api/assets/{asset_id}/signed-url
- returns: { url, expires_at }
- must enforce permissions (org + dataset published + ACL)

## 5) Ingestion (publisher only)
POST /api/ingest/datasets
- body: { name, description?, tags? }
- returns: { dataset_id, status:draft }

POST /api/ingest/assets:batch
- body: { dataset_id, files: [{ filename, kind, content_type, byte_size }] }
- returns: [{ asset_id, upload_url, storage_key }]

POST /api/ingest/datasets/{dataset_id}/publish
- body: { manifest: {...} }
- validates schema + assets exist, creates items + annotations, marks published

### Manifest shape (high level)
{
  "items": [
    {
      "type": "image_pair_compare",
      "title": "...",
      "summary": "...",
      "payload": { ... },
      "annotations": [
        { "schema": "timeline_v1", "data": { ... } }
      ]
    }
  ]
}

## 6) Admin (admin/publisher only)
GET /api/admin/datasets/{dataset_id}/shares
- returns: [{ user_id?, email, access_role, created_at, pending? }]; pending=true when shared with email that has no account yet

POST /api/admin/datasets/{dataset_id}/shares
- body: { email, access_role: "viewer" }
- if user exists in same org: insert dataset_access; else insert pending_dataset_share (applied when they sign up). Idempotent.

DELETE /api/admin/datasets/{dataset_id}/shares/{user_id}
- remove dataset_access row

DELETE /api/admin/datasets/{dataset_id}/shares/pending?email=...
- remove pending_dataset_share row

## 7) Errors
- 400: bad request (e.g. empty manifest)
- 401: unauthenticated
- 403: unauthorized (wrong org/role, invalid/expired token)
- 404: not found (do not leak existence across orgs)
- 409: conflict / illegal state (e.g. dataset already published, upload to published dataset)
- 422: validation error (manifest/schema). Body: `{ "errors": [ { "path", "error_type", "message" } ] }`