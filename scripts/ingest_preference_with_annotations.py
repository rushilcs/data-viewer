#!/usr/bin/env python3
"""
Ingestion pipeline: join Convex snapshot annotator responses with the preference dataset,
then create a dataset in the data viewer with image_pair_compare items (A vs B screenshots + annotations).

- Annotations live in snapshot_grandiose* (Convex export), NOT in preference_dataset.
- Join: snapshot tasks (with curAnnotation) + media (taskId -> A/B, model name) -> prompt_id from media s3Key.
- Screenshots are read from preference_dataset/screenshots/ (local); asset paths use prompt_id and model slug.

Usage:
  export DATA_VIEWER_BASE_URL=http://localhost:8000
  export DATA_VIEWER_EMAIL=...
  export DATA_VIEWER_PASSWORD=...
  python scripts/ingest_preference_with_annotations.py [--data-dir data_example] [--dry-run]
  python scripts/ingest_preference_with_annotations.py --limit 100   # ingest only 100 items (for testing)

Optional: --no-ingest to only build and print the joined manifest (no API calls).
Optional: --limit N to ingest only the first N annotated items (e.g. 100 for testing).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Add project root so we can import from sdk
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sdk.dataset_uploader.client import DatasetClient


# Media s3Key pattern: run_2/prompt_1550/GPT-5.2_6738.png -> prompt_id 1550
PROMPT_ID_FROM_S3 = re.compile(r"prompt_(\d+)")


def _media_name_to_slug(media_name: str, model_info: dict) -> str | None:
    """Map mediaName (e.g. 'GPT-5.2.png') to model slug (e.g. 'gpt-5.2') using dataset model_info."""
    name = (media_name or "").removesuffix(".png").strip()
    if not name:
        return None
    for slug, info in (model_info or {}).items():
        if info.get("filename_key") == name:
            return slug
    return None


def load_preference_dataset(pref_dir: Path) -> dict:
    """Load preference_dataset/dataset.json. Pref dir is the folder containing dataset.json."""
    path = pref_dir / "dataset.json"
    if not path.exists():
        raise FileNotFoundError(f"Preference dataset not found: {path}")
    # Prefer jq to extract only model_info + slim prompts (prompt_id, description, generation keys)
    # to avoid loading the full ~5MB JSON into memory
    import subprocess
    jq_prog = (
        "{model_info, prompts: [.prompts[]? | "
        "{prompt_id, description, generations: (.generations | keys)}]}"
    )
    try:
        out = subprocess.run(
            ["jq", "-c", jq_prog, str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if out.returncode == 0 and out.stdout:
            return json.loads(out.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    # Fallback: load full file (requires sufficient memory for ~5MB JSON)
    return json.loads(path.read_text())


def load_jsonl(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def find_snapshot_dir(data_dir: Path) -> Path | None:
    """Locate snapshot_grandiose* folder under data_dir."""
    data_dir = data_dir.resolve()
    if not data_dir.is_dir():
        return None
    for child in data_dir.iterdir():
        if child.is_dir() and child.name.startswith("snapshot_grandiose"):
            return child
    return None


def build_joined_items(
    pref_dir: Path,
    snapshot_dir: Path,
    pref_data: dict,
) -> tuple[list[dict], list[tuple[int, str]]]:
    """
    Join snapshot tasks + media with preference dataset.
    Returns (list of item dicts, list of (prompt_id, slug) for assets).
    Each item: { prompt_id, slug_a, slug_b, prompt_text, annotation }
    """
    model_info = pref_data.get("model_info") or {}
    prompts_by_id = {p["prompt_id"]: p for p in pref_data.get("prompts") or []}
    total_prompts = len(prompts_by_id)

    tasks_path = snapshot_dir / "tasks" / "documents.jsonl"
    media_path = snapshot_dir / "media" / "documents.jsonl"
    if not tasks_path.exists() or not media_path.exists():
        raise FileNotFoundError(f"Snapshot tasks or media not found under {snapshot_dir}")

    tasks = load_jsonl(tasks_path)
    media_rows = load_jsonl(media_path)

    # taskId -> [(groupLabel, mediaName, s3Key), ...]
    media_by_task: dict[str, list[tuple[str, str, str]]] = {}
    for row in media_rows:
        tid = (row.get("taskId") or "").strip()
        if not tid:
            continue
        label = (row.get("groupLabel") or "").strip().upper()
        name = (row.get("mediaName") or "").strip()
        s3_key = (row.get("s3Key") or "").strip()
        if label in ("A", "B") and name:
            media_by_task.setdefault(tid, []).append((label, name, s3_key))

    items: list[dict] = []
    asset_keys: set[tuple[int, str]] = set()

    for task in tasks:
        if (task.get("status") or "") != "CO":
            continue
        ann = task.get("curAnnotation")
        if not ann or not isinstance(ann, dict):
            continue
        task_id = (task.get("_id") or "").strip()
        if not task_id:
            continue
        pairs = media_by_task.get(task_id)
        if not pairs or len(pairs) != 2:
            continue
        by_label = {label: (name, s3_key) for label, name, s3_key in pairs}
        a_row = by_label.get("A")
        b_row = by_label.get("B")
        if not a_row or not b_row:
            continue
        name_a, s3_a = a_row
        name_b, s3_b = b_row
        prompt_id = None
        for _, sk in [a_row, b_row]:
            m = PROMPT_ID_FROM_S3.search(sk)
            if m:
                prompt_id = int(m.group(1))
                break
        if prompt_id is None or prompt_id < 0 or prompt_id >= total_prompts:
            continue
        slug_a = _media_name_to_slug(name_a, model_info)
        slug_b = _media_name_to_slug(name_b, model_info)
        if not slug_a or not slug_b:
            continue
        gens = (prompts_by_id.get(prompt_id) or {}).get("generations")
        if isinstance(gens, dict):
            gens_set = set(gens)
        else:
            gens_set = set(gens or [])
        if slug_a not in gens_set or slug_b not in gens_set:
            continue
        prompt_record = prompts_by_id.get(prompt_id) or {}
        prompt_text = prompt_record.get("description") or f"Prompt {prompt_id}"

        items.append({
            "prompt_id": prompt_id,
            "slug_a": slug_a,
            "slug_b": slug_b,
            "prompt_text": prompt_text,
            "annotation": ann,
        })
        asset_keys.add((prompt_id, slug_a))
        asset_keys.add((prompt_id, slug_b))

    return items, sorted(asset_keys)


def build_manifest_items(
    joined_items: list[dict],
    filename_to_asset_id: dict[str, str],
    pref_dir: Path,
) -> list[dict]:
    """Build manifest items (image_pair_compare) and resolve asset IDs from uploaded filenames."""
    manifest_items = []
    for i, row in enumerate(joined_items):
        prompt_id = row["prompt_id"]
        slug_a, slug_b = row["slug_a"], row["slug_b"]
        prompt_text = row["prompt_text"]
        ann = row["annotation"]
        # Filenames as produced by preference_dataset: screenshots/0000_gpt-5.2.png
        fname_a = f"{prompt_id:04d}_{slug_a}.png"
        fname_b = f"{prompt_id:04d}_{slug_b}.png"
        left_asset_id = filename_to_asset_id.get(fname_a)
        right_asset_id = filename_to_asset_id.get(fname_b)
        if not left_asset_id or not right_asset_id:
            raise ValueError(f"Missing asset IDs for {fname_a} / {fname_b}")
        payload = {
            "left_asset_id": left_asset_id,
            "right_asset_id": right_asset_id,
            "prompt": prompt_text,
            "metadata": {
                "prompt_id": prompt_id,
                "option_a_model": slug_a,
                "option_b_model": slug_b,
                "annotation": ann,
            },
        }
        manifest_items.append({
            "type": "image_pair_compare",
            "title": f"Prompt {prompt_id}: {slug_a} vs {slug_b}",
            "summary": (ann.get("explanation") or "")[:200] or None,
            "payload": payload,
            "annotations": [],  # Backend only allows timeline_v1/captions_v1; annotation is in payload.metadata
        })
    return manifest_items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data_example"),
        help="Directory containing preference_dataset and snapshot_grandiose*",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build join and manifest only; do not create dataset or upload",
    )
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Same as --dry-run: only build and print joined data / manifest",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Ingest only the first N annotated items (e.g. 100 for testing). No limit if omitted.",
    )
    parser.add_argument(
        "--dataset-name",
        default="Web design preference (with annotations)",
        help="Name of the dataset to create",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DATA_VIEWER_BASE_URL", "http://localhost:8000"),
        help="Data viewer API base URL",
    )
    parser.add_argument(
        "--email",
        default=os.environ.get("DATA_VIEWER_EMAIL"),
        help="Login email (or set DATA_VIEWER_EMAIL)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("DATA_VIEWER_PASSWORD"),
        help="Login password (or set DATA_VIEWER_PASSWORD)",
    )
    args = parser.parse_args()

    data_dir = args.data_dir if args.data_dir.is_absolute() else (ROOT / args.data_dir)
    pref_dir = data_dir / "preference_dataset"
    snapshot_dir = find_snapshot_dir(data_dir)

    if not pref_dir.is_dir():
        print(f"Preference dataset directory not found: {pref_dir}", file=sys.stderr)
        return 1
    if not snapshot_dir:
        print(f"Snapshot folder (snapshot_grandiose*) not found under {data_dir}", file=sys.stderr)
        return 1

    print("Loading preference dataset...", file=sys.stderr)
    pref_data = load_preference_dataset(pref_dir)
    print("Building joined items (snapshot tasks + media -> preference)...", file=sys.stderr)
    joined_items, asset_keys = build_joined_items(pref_dir, snapshot_dir, pref_data)
    if args.limit is not None:
        if args.limit <= 0:
            print("--limit must be positive.", file=sys.stderr)
            return 1
        joined_items = joined_items[: args.limit]
        # Recompute asset keys from the limited set so we only upload those screenshots
        asset_keys = sorted({(r["prompt_id"], r["slug_a"]) for r in joined_items} | {(r["prompt_id"], r["slug_b"]) for r in joined_items})
    print(f"Joined items: {len(joined_items)}, unique assets: {len(asset_keys)}", file=sys.stderr)

    if not joined_items:
        print("No completed annotated tasks found. Exiting.", file=sys.stderr)
        return 0

    screenshots_dir = pref_dir / "screenshots"
    if not screenshots_dir.is_dir():
        print(f"Screenshots directory not found: {screenshots_dir}", file=sys.stderr)
        return 1

    # Local paths for each (prompt_id, slug) -> Path
    asset_paths: list[Path] = []
    filename_order: list[str] = []
    for prompt_id, slug in asset_keys:
        fname = f"{prompt_id:04d}_{slug}.png"
        path = screenshots_dir / fname
        if not path.exists():
            print(f"Missing screenshot: {path}", file=sys.stderr)
            return 1
        asset_paths.append(path)
        filename_order.append(fname)

    if args.dry_run or args.no_ingest:
        # Build a mock filename -> asset_id so we can still build manifest for inspection
        filename_to_asset_id = {f: f"dry-run-{i}" for i, f in enumerate(filename_order)}
        manifest_items = build_manifest_items(joined_items, filename_to_asset_id, pref_dir)
        print(json.dumps({"items": manifest_items}, indent=2))
        print(f"\nDry run: would upload {len(asset_paths)} assets and publish {len(manifest_items)} items.", file=sys.stderr)
        return 0

    if not args.email or not args.password:
        print("For ingest, set --email and --password (or DATA_VIEWER_EMAIL and DATA_VIEWER_PASSWORD).", file=sys.stderr)
        return 1

    client = DatasetClient(base_url=args.base_url, email=args.email, password=args.password)
    try:
        client.login()
    except Exception as e:
        print(f"Login failed: {e}", file=sys.stderr)
        return 1

    print("Creating draft dataset...", file=sys.stderr)
    create_resp = client.create_dataset(
        name=args.dataset_name,
        description="Preference comparisons (A vs B) with annotator responses from Convex snapshot.",
        tags=["preference", "web-design", "annotations"],
    )
    dataset_id = create_resp["dataset_id"]
    print(f"Dataset ID: {dataset_id}", file=sys.stderr)

    print(f"Uploading {len(asset_paths)} assets (batch)...", file=sys.stderr)
    try:
        result = client.upload_assets(dataset_id, asset_paths, kind_hint="image")
    except Exception as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        return 1
    # Client returns filename -> asset_id (e.g. "0123_gpt-5.2.png" -> uuid)
    filename_to_asset_id = dict(result)

    manifest_items = build_manifest_items(joined_items, filename_to_asset_id, pref_dir)
    manifest = {"items": manifest_items}

    print("Publishing dataset...", file=sys.stderr)
    try:
        pub = client.publish(dataset_id, manifest)
        print(f"Published: {pub}", file=sys.stderr)
    except Exception as e:
        print(f"Publish failed: {e}", file=sys.stderr)
        return 1

    print(f"Done. Dataset {dataset_id} has {len(manifest_items)} items.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
