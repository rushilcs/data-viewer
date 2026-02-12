"""CLI: dataset-uploader create | upload | publish."""
import argparse
import json
import sys
from pathlib import Path

from .client import DatasetClient


def main() -> int:
    parser = argparse.ArgumentParser(prog="dataset-uploader", description="Upload datasets to the viewer API")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--email", required=True, help="Login email")
    parser.add_argument("--password", required=True, help="Login password")
    sub = parser.add_subparsers(dest="command", required=True)

    # create
    p_create = sub.add_parser("create", help="Create a draft dataset")
    p_create.add_argument("--name", required=True, help="Dataset name")
    p_create.add_argument("--description", default=None, help="Dataset description")
    p_create.add_argument("--tags", nargs="*", default=None, help="Tags")
    p_create.set_defaults(func=cmd_create)

    # upload
    p_upload = sub.add_parser("upload", help="Upload assets to a draft dataset")
    p_upload.add_argument("--dataset-id", required=True, help="Draft dataset UUID")
    p_upload.add_argument("files", nargs="+", help="Local file paths to upload")
    p_upload.add_argument("--kind", choices=["image", "video", "audio", "other"], default=None, help="Kind for all files")
    p_upload.set_defaults(func=cmd_upload)

    # publish
    p_publish = sub.add_parser("publish", help="Publish dataset with manifest")
    p_publish.add_argument("--dataset-id", required=True, help="Dataset UUID")
    p_publish.add_argument("--manifest", required=True, help="Path to manifest.json")
    p_publish.set_defaults(func=cmd_publish)

    args = parser.parse_args()
    client = DatasetClient(base_url=args.base_url, email=args.email, password=args.password)
    try:
        client.login()
        return args.func(client, args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        client.close()


def cmd_create(client: DatasetClient, args: argparse.Namespace) -> int:
    out = client.create_dataset(
        name=args.name,
        description=args.description,
        tags=args.tags,
    )
    print(json.dumps(out, indent=2))
    print(f"Created dataset_id: {out['dataset_id']}", file=sys.stderr)
    return 0


def cmd_upload(client: DatasetClient, args: argparse.Namespace) -> int:
    paths = [Path(f) for f in args.files]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"Missing files: {missing}", file=sys.stderr)
        return 1
    result = client.upload_assets(args.dataset_id, paths, kind_hint=args.kind)
    print(json.dumps(result, indent=2))
    for name, aid in result.items():
        print(f"  {name} -> {aid}", file=sys.stderr)
    return 0


def cmd_publish(client: DatasetClient, args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    manifest_dict = json.loads(manifest_path.read_text())
    if "items" not in manifest_dict:
        print("Manifest must contain 'items' key", file=sys.stderr)
        return 1
    out = client.publish(args.dataset_id, manifest_dict)
    print(json.dumps(out, indent=2))
    print(f"Published {out['item_count']} items", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
