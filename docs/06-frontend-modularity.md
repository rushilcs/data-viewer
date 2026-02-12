# FILE: docs/06-frontend-modularity.md

# Frontend Modularity

## 1) Viewer Registry Pattern
A central registry maps item.type -> viewer module.

Example contract:
- viewerRegistry[type] = {
  Component,
  getSummary(item),
  validatePayload(payload) (optional on client; server is authoritative)
}

## 2) Shared UI Primitives
- MetadataPanel: renders prompt + metadata safely
- AssetLoader: takes asset_id, calls signed-url endpoint, caches short-term in-memory
- Timeline: renders time-based annotations for video/audio
- Gallery: grid of images with rank indicators

## 3) Pages
- /login
- /datasets
- /datasets/[datasetId]
- /items/[itemId]

## 4) Data Fetching
- Server-side pagination for dataset items
- Item detail fetch returns:
  - item payload
  - asset metadata for referenced assets
  - annotations required by viewer type

## 5) Adding New Item Types
Steps:
1) Define schema in docs/03-item-schemas.md
2) Add backend validation for schema
3) Add new viewer component and register in viewerRegistry
4) Add tests (golden fixtures)