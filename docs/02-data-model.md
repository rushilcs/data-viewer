# FILE: docs/02-data-model.md

# Data Model (Postgres)

## 1) Tables

### organizations
- id (uuid, pk)
- name (text)
- created_at (timestamptz)

### users
- id (uuid, pk)
- org_id (uuid, fk -> organizations.id)
- email (citext, unique within org or globally unique)
- password_hash (text) OR external auth subject
- role (enum: admin, viewer, publisher) [v1 can use admin/viewer]
- is_active (bool)
- created_at (timestamptz)

### datasets
- id (uuid, pk)
- org_id (uuid, fk)
- name (text)
- description (text)
- status (enum: draft, published, archived)
- created_by_user_id (uuid, fk -> users.id)
- created_at (timestamptz)
- published_at (timestamptz, nullable)
- tags (text[], optional)

### dataset_access
- id (uuid, pk)
- org_id (uuid, fk -> organizations.id)
- dataset_id (uuid, fk -> datasets.id)
- user_id (uuid, fk -> users.id)
- access_role (enum: "viewer" | "editor")
- created_by_user_id (uuid, fk -> users.id)
- created_at (timestamptz)
- UNIQUE(dataset_id, user_id)
- org_id must match dataset.org_id and user.org_id
- Indexes: (org_id, user_id), (org_id, dataset_id)

### invites
- (legacy; open signup uses pending_dataset_share instead)

### pending_dataset_share
- id (uuid, pk)
- org_id (uuid, fk -> organizations.id)
- dataset_id (uuid, fk -> datasets.id)
- email (citext)
- access_role (text, default viewer)
- created_by_user_id (uuid, fk -> users.id)
- created_at (timestamptz)
- UNIQUE(dataset_id, email)
- Index: (org_id, email)
- When user signs up with that email (in that org), rows are converted to dataset_access and deleted.

### items
- id (uuid, pk)
- org_id (uuid, fk)
- dataset_id (uuid, fk)
- type (text)  # matches ItemType registry
- title (text, nullable)
- summary (text, nullable) # brief rendering in list
- payload (jsonb)          # validated by schema per type
- created_at (timestamptz)

### assets
- id (uuid, pk)
- org_id (uuid, fk)
- dataset_id (uuid, fk)
- item_id (uuid, fk, nullable) # some assets may be dataset-level; v1 can tie to item
- kind (enum: image, video, audio, other)
- storage_key (text)      # S3 key
- content_type (text)
- byte_size (bigint)
- sha256 (text, nullable)
- created_at (timestamptz)

### annotations
- id (uuid, pk)
- org_id (uuid, fk)
- dataset_id (uuid, fk)
- item_id (uuid, fk)
- schema (text)           # e.g. "timeline_v1", "captions_v1"
- data (jsonb)            # time-aligned events, captions, etc.
- created_at (timestamptz)

### audit_events
- id (uuid, pk)
- org_id (uuid, fk)
- user_id (uuid, fk)
- event_type (text)       # login_success, view_dataset, view_item, mint_asset_url, publish_dataset
- event_data (jsonb)
- ip (inet, nullable)
- user_agent (text, nullable)
- created_at (timestamptz)

## 2) Indexes (minimum)
- datasets: (org_id, status, created_at desc)
- items: (org_id, dataset_id, created_at desc)
- items: (org_id, dataset_id, type, created_at desc)
- assets: (org_id, dataset_id, item_id)
- annotations: (org_id, item_id)

## 3) Access rules
- Admin/publisher: can see all datasets in their org; can create invites; can share datasets via dataset_access.
- Viewer: can only see datasets that have a dataset_access row for (dataset_id, user_id).
- Item, asset, and annotation access is derived from dataset access (never by direct ID).

## 4) Notes
- payload is jsonb but must be validated against per-type schemas at publish time and on item fetch.
- Prefer immutability after publish: editing should create a new dataset version or new item version (v2).