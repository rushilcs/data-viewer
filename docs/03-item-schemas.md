# FILE: docs/03-item-schemas.md

# Item Schemas (v1)

This document defines the JSON payload schema for each item.type. Payload is stored in items.payload and validated at publish time.

All items share an envelope in the DB. The payload below is type-specific.

## Common Conventions
- asset references use asset_id (uuid) OR storage_key. v1 should standardize on asset_id once created.
- metadata is freeform but must be JSON-serializable.
- prompt fields should be plain text.

---

## 1) image_pair_compare
Required:
- left_asset_id: uuid
- right_asset_id: uuid
- prompt: string
Optional:
- metadata: object

Example:
{
  "left_asset_id": "uuid",
  "right_asset_id": "uuid",
  "prompt": "Build a landing page for ...",
  "metadata": {
    "model": "gpt-4.1",
    "seed": 123,
    "run_id": "abc"
  }
}

---

## 2) image_ranked_gallery
Required:
- asset_ids: uuid[] (length >= 2)
- prompt: string
- rankings: object
  - method: "pairwise" | "full_rank" | "scores"
  - data: any (validated shape below)
Optional:
- metadata: object

Rankings shapes:
A) full_rank
{
  "method": "full_rank",
  "data": {
    "order": ["asset_id_3", "asset_id_1", "asset_id_2"],
    "annotator_count": 5
  }
}

B) scores
{
  "method": "scores",
  "data": {
    "scores": {
      "asset_id_1": 0.72,
      "asset_id_2": 0.55
    },
    "scale": "0-1"
  }
}

---

## 3) video_with_timeline
Required:
- video_asset_id: uuid
Optional:
- poster_image_asset_id: uuid
- metadata: object

Timeline annotations live in annotations table with schema="timeline_v1"

Example payload:
{
  "video_asset_id": "uuid",
  "poster_image_asset_id": "uuid",
  "metadata": { "prompt": "...", "run_id": "..." }
}

---

## 4) audio_with_captions
Required:
- audio_asset_id: uuid
Optional:
- metadata: object

Captions/transcript live in annotations table with schema="captions_v1"

Example payload:
{
  "audio_asset_id": "uuid",
  "metadata": { "language": "en-US" }
}