"""Ingestion: create draft, batch upload URLs, PUT upload, publish. Publisher-only."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.deps import require_csrf, require_publisher, get_current_user_optional, get_asset_for_user, get_dataset_for_user
from app.core.security import verify_upload_token
from app.db import get_db, Dataset, Asset, Item, Annotation, User
from app.api.schemas import (
    IngestCreateDatasetRequest,
    IngestCreateDatasetResponse,
    IngestAssetsBatchRequest,
    IngestAssetUploadUrlResponse,
    PublishRequest,
    PublishResponse,
    ManifestValidationErrorItem,
)
from app.services.upload_validation import validate_file_spec, sanitize_storage_filename
from app.services.storage import get_storage
from app.core.rate_limit import is_ingest_rate_limited
from app.services.item_registry import (
    validate_payload,
    extract_asset_ids,
    validate_annotation,
    get_supported_item_types,
)
from app.services.audit import log_audit
from app.core.metrics import record_publish_success, record_publish_failure

router = APIRouter(prefix="/ingest", tags=["ingest"])
settings = get_settings()


def _validation_errors_from_pydantic(err: ValidationError, item_prefix: str) -> list[ManifestValidationErrorItem]:
    """Turn Pydantic ValidationError into list of path, error_type, message."""
    out = []
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"])
        path = f"{item_prefix}.{loc}" if loc else item_prefix
        err_type = e.get("type", "validation_error")
        msg = e.get("msg", str(e))
        if "extra" in err_type or "forbid" in str(msg).lower():
            err_type = "extra_forbidden"
        elif "missing" in err_type:
            err_type = "missing_required"
        elif "type" in err_type or "literal" in err_type:
            err_type = "wrong_type"
        out.append(ManifestValidationErrorItem(path=path, error_type=err_type, message=msg))
    return out


@router.post("/datasets", response_model=IngestCreateDatasetResponse, dependencies=[Depends(require_csrf)])
async def create_draft_dataset(
    body: IngestCreateDatasetRequest,
    user: User = Depends(require_publisher),
    db: AsyncSession = Depends(get_db),
):
    if is_ingest_rate_limited(str(user.id)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    dataset = Dataset(
        org_id=user.org_id,
        name=body.name,
        description=body.description,
        status="draft",
        created_by_user_id=user.id,
        tags=body.tags,
    )
    db.add(dataset)
    await db.flush()
    return IngestCreateDatasetResponse(dataset_id=dataset.id, status="draft")


@router.post(
    "/assets:batch",
    response_model=list[IngestAssetUploadUrlResponse],
    dependencies=[Depends(require_csrf)],
)
async def batch_upload_urls(
    request: Request,
    body: IngestAssetsBatchRequest,
    user: User = Depends(require_publisher),
    db: AsyncSession = Depends(get_db),
):
    if is_ingest_rate_limited(str(user.id)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    dataset = await get_dataset_for_user(body.dataset_id, user, db)
    # Allow draft (initial ingest) or published (append: add new assets then append items)
    if dataset.status not in ("draft", "published"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dataset must be draft or published to upload assets",
        )
    out = []
    base = str(request.base_url).rstrip("/")
    storage = get_storage()
    ttl = settings.upload_token_ttl_seconds
    for spec in body.files:
        try:
            validate_file_spec(spec.kind, spec.content_type, spec.byte_size)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
        asset_id = uuid4()
        safe_name = sanitize_storage_filename(spec.filename)
        key_suffix = f"{uuid4().hex}_{safe_name}" if safe_name else uuid4().hex
        storage_key = f"{user.org_id}/{body.dataset_id}/{key_suffix}"
        asset = Asset(
            id=asset_id,
            org_id=user.org_id,
            dataset_id=body.dataset_id,
            item_id=None,
            kind=spec.kind,
            storage_key=storage_key,
            content_type=spec.content_type,
            byte_size=spec.byte_size,
        )
        db.add(asset)
        await db.flush()
        upload_url = storage.create_presigned_put(
            storage_key,
            spec.content_type,
            spec.byte_size,
            ttl,
            asset_id=asset_id,
            org_id=user.org_id,
            dataset_id=body.dataset_id,
            base_url=base,
        )
        out.append(
            IngestAssetUploadUrlResponse(
                asset_id=asset_id,
                upload_url=upload_url,
                storage_key=storage_key,
            )
        )
    return out


@router.put("/assets/{asset_id}/upload", status_code=204)
async def upload_asset(
    asset_id: UUID,
    token: str,
    request: Request,
    user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    # Authenticate: either session (cookie) or valid upload token (token-only for cross-origin PUT when cookies aren't sent)
    if user is not None:
        if user.role not in ("admin", "publisher"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Publisher or admin role required")
        asset = await get_asset_for_user(asset_id, user, db)
    else:
        result = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        if not verify_upload_token(token, asset_id, asset.org_id, asset.dataset_id, asset.byte_size):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired upload token")
    ds_result = await db.execute(
        select(Dataset).where(
            Dataset.id == asset.dataset_id,
            Dataset.org_id == asset.org_id,
            Dataset.status.in_(["draft", "published"]),
        )
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dataset must be draft or published",
        )
    # For published datasets, only allow upload for assets not yet linked to an item (append flow)
    if asset.item_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset already linked to an item",
        )
    if not verify_upload_token(token, asset_id, asset.org_id, asset.dataset_id, asset.byte_size):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired token")
    # Read body and check size (PUT body = raw file bytes)
    content = await request.body()
    if len(content) != asset.byte_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Size mismatch: expected {asset.byte_size}, got {len(content)}",
        )
    if getattr(settings, "enable_av_scan", False):
        from app.services.av_scan import scan_upload
        if not scan_upload(content, asset.content_type or "", asset.storage_key):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File did not pass security scan",
            )
    assets_dir = Path(settings.dev_assets_dir)
    file_path = assets_dir / asset.storage_key
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(content)
    return None


@router.post(
    "/datasets/{dataset_id}/publish",
    response_model=PublishResponse,
    dependencies=[Depends(require_csrf)],
)
async def publish_dataset(
    dataset_id: UUID,
    body: PublishRequest,
    user: User = Depends(require_publisher),
    db: AsyncSession = Depends(get_db),
):
    if not settings.ingest_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion is temporarily disabled",
        )
    if is_ingest_rate_limited(str(user.id)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    dataset = await get_dataset_for_user(dataset_id, user, db)
    if dataset.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dataset already published",
        )

    manifest = body.manifest
    if not manifest.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manifest must contain at least one item",
        )

    supported = set(get_supported_item_types())
    asset_ids_in_dataset: set[UUID] = set()
    validation_errors: list[ManifestValidationErrorItem] = []

    # 1) Validate manifest shape and all items (no DB writes yet)
    assets_result = await db.execute(
        select(Asset.id).where(
            Asset.org_id == user.org_id,
            Asset.dataset_id == dataset_id,
        )
    )
    asset_ids_in_dataset = set(assets_result.scalars().all())

    for i, mitem in enumerate(manifest.items):
        prefix = f"items[{i}]"
        if mitem.type not in supported:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path=prefix,
                    error_type="unsupported_type",
                    message=f"Unsupported item type '{mitem.type}'",
                )
            )
            continue
        try:
            validate_payload(mitem.type, mitem.payload)
        except ValidationError as e:
            validation_errors.extend(_validation_errors_from_pydantic(e, f"{prefix}.payload"))
            continue
        except ValueError as e:
            validation_errors.append(
                ManifestValidationErrorItem(path=f"{prefix}.payload", error_type="invalid", message=str(e))
            )
            continue
        ref_ids = set(extract_asset_ids(mitem.type, mitem.payload))
        missing = ref_ids - asset_ids_in_dataset
        if missing:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path=prefix,
                    error_type="asset_not_uploaded",
                    message=f"Assets not uploaded for this dataset: {sorted(str(x) for x in missing)}",
                )
            )
        for j, ann in enumerate(mitem.annotations):
            try:
                validate_annotation(ann.schema, ann.data)
            except ValidationError as e:
                validation_errors.extend(
                    _validation_errors_from_pydantic(e, f"{prefix}.annotations[{j}]")
                )
            except ValueError as e:
                validation_errors.append(
                    ManifestValidationErrorItem(
                        path=f"{prefix}.annotations[{j}]",
                        error_type="invalid_annotation",
                        message=str(e),
                    )
                )

    # Integrity: referenced assets must exist in storage with matching size (and content_type where available)
    referenced_asset_ids: set[UUID] = set()
    for mitem in manifest.items:
        referenced_asset_ids |= set(extract_asset_ids(mitem.type, mitem.payload))
    storage = get_storage()
    for aid in referenced_asset_ids:
        if aid not in asset_ids_in_dataset:
            continue
        asset_row = (await db.execute(select(Asset).where(Asset.id == aid, Asset.org_id == user.org_id, Asset.dataset_id == dataset_id))).scalar_one_or_none()
        if not asset_row:
            continue
        try:
            meta = storage.head_object(asset_row.storage_key)
        except FileNotFoundError:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path="assets",
                    error_type="asset_missing_in_storage",
                    message=f"Asset {aid} not found in storage",
                )
            )
            continue
        if meta.get("content_length") is not None and meta["content_length"] != asset_row.byte_size:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path="assets",
                    error_type="asset_size_mismatch",
                    message=f"Asset {aid}: expected size {asset_row.byte_size}, got {meta['content_length']}",
                )
            )
        if meta.get("content_type") is not None and meta["content_type"] != asset_row.content_type:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path="assets",
                    error_type="asset_content_type_mismatch",
                    message=f"Asset {aid}: expected type {asset_row.content_type}, got {meta['content_type']}",
                )
            )

    if validation_errors:
        record_publish_failure()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": [e.model_dump() for e in validation_errors]},
        )

    # 2) Atomic: create items, annotations, mark published
    now = datetime.now(timezone.utc)
    for mitem in manifest.items:
        item_id = uuid4()
        item = Item(
            id=item_id,
            org_id=user.org_id,
            dataset_id=dataset_id,
            type=mitem.type,
            title=mitem.title,
            summary=mitem.summary,
            payload=mitem.payload,
        )
        db.add(item)
        await db.flush()
        for ann in mitem.annotations:
            ann_row = Annotation(
                org_id=user.org_id,
                dataset_id=dataset_id,
                item_id=item_id,
                schema=ann.schema,
                data=ann.data,
            )
            db.add(ann_row)
        # Link assets to this item (update item_id)
        ref_ids = list(extract_asset_ids(mitem.type, mitem.payload))
        if ref_ids:
            await db.execute(
                update(Asset)
                .where(
                    Asset.org_id == user.org_id,
                    Asset.dataset_id == dataset_id,
                    Asset.id.in_(ref_ids),
                )
                .values(item_id=item_id)
            )
    dataset.status = "published"
    dataset.published_at = now
    await db.flush()
    await log_audit(
        db,
        user.id,
        user.org_id,
        "publish_dataset",
        event_data={"dataset_id": str(dataset_id), "item_count": len(manifest.items)},
    )
    record_publish_success()
    return PublishResponse(
        dataset_id=dataset_id,
        status="published",
        item_count=len(manifest.items),
    )


@router.post(
    "/datasets/{dataset_id}/append",
    response_model=PublishResponse,
    dependencies=[Depends(require_csrf)],
)
async def append_dataset(
    dataset_id: UUID,
    body: PublishRequest,
    user: User = Depends(require_publisher),
    db: AsyncSession = Depends(get_db),
):
    """Append new items to an already-published dataset. New assets must have been uploaded first (unlinked)."""
    if not settings.ingest_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion is temporarily disabled",
        )
    if is_ingest_rate_limited(str(user.id)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    dataset = await get_dataset_for_user(dataset_id, user, db)
    if dataset.status != "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Can only append to a published dataset",
        )

    manifest = body.manifest
    if not manifest.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manifest must contain at least one item",
        )

    supported = set(get_supported_item_types())
    validation_errors: list[ManifestValidationErrorItem] = []

    # Only unlinked assets in this dataset are valid for new items
    assets_result = await db.execute(
        select(Asset.id).where(
            Asset.org_id == user.org_id,
            Asset.dataset_id == dataset_id,
            Asset.item_id.is_(None),
        )
    )
    asset_ids_in_dataset = set(assets_result.scalars().all())

    for i, mitem in enumerate(manifest.items):
        prefix = f"items[{i}]"
        if mitem.type not in supported:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path=prefix,
                    error_type="unsupported_type",
                    message=f"Unsupported item type '{mitem.type}'",
                )
            )
            continue
        try:
            validate_payload(mitem.type, mitem.payload)
        except ValidationError as e:
            validation_errors.extend(_validation_errors_from_pydantic(e, f"{prefix}.payload"))
            continue
        except ValueError as e:
            validation_errors.append(
                ManifestValidationErrorItem(path=f"{prefix}.payload", error_type="invalid", message=str(e))
            )
            continue
        ref_ids = set(extract_asset_ids(mitem.type, mitem.payload))
        missing = ref_ids - asset_ids_in_dataset
        if missing:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path=prefix,
                    error_type="asset_not_uploaded",
                    message=f"Assets not uploaded for this dataset (append): {sorted(str(x) for x in missing)}",
                )
            )
        for j, ann in enumerate(mitem.annotations):
            try:
                validate_annotation(ann.schema, ann.data)
            except ValidationError as e:
                validation_errors.extend(
                    _validation_errors_from_pydantic(e, f"{prefix}.annotations[{j}]")
                )
            except ValueError as e:
                validation_errors.append(
                    ManifestValidationErrorItem(
                        path=f"{prefix}.annotations[{j}]",
                        error_type="invalid_annotation",
                        message=str(e),
                    )
                )

    # Integrity: referenced assets must exist in storage with matching size/type
    referenced_asset_ids_append: set[UUID] = set()
    for mitem in manifest.items:
        referenced_asset_ids_append |= set(extract_asset_ids(mitem.type, mitem.payload))
    storage_append = get_storage()
    for aid in referenced_asset_ids_append:
        if aid not in asset_ids_in_dataset:
            continue
        asset_row = (await db.execute(select(Asset).where(Asset.id == aid, Asset.org_id == user.org_id, Asset.dataset_id == dataset_id))).scalar_one_or_none()
        if not asset_row:
            continue
        try:
            meta = storage_append.head_object(asset_row.storage_key)
        except FileNotFoundError:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path="assets",
                    error_type="asset_missing_in_storage",
                    message=f"Asset {aid} not found in storage",
                )
            )
            continue
        if meta.get("content_length") is not None and meta["content_length"] != asset_row.byte_size:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path="assets",
                    error_type="asset_size_mismatch",
                    message=f"Asset {aid}: expected size {asset_row.byte_size}, got {meta['content_length']}",
                )
            )
        if meta.get("content_type") is not None and meta["content_type"] != asset_row.content_type:
            validation_errors.append(
                ManifestValidationErrorItem(
                    path="assets",
                    error_type="asset_content_type_mismatch",
                    message=f"Asset {aid}: expected type {asset_row.content_type}, got {meta['content_type']}",
                )
            )

    if validation_errors:
        record_publish_failure()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": [e.model_dump() for e in validation_errors]},
        )

    now = datetime.now(timezone.utc)
    for mitem in manifest.items:
        item_id = uuid4()
        item = Item(
            id=item_id,
            org_id=user.org_id,
            dataset_id=dataset_id,
            type=mitem.type,
            title=mitem.title,
            summary=mitem.summary,
            payload=mitem.payload,
        )
        db.add(item)
        await db.flush()
        for ann in mitem.annotations:
            ann_row = Annotation(
                org_id=user.org_id,
                dataset_id=dataset_id,
                item_id=item_id,
                schema=ann.schema,
                data=ann.data,
            )
            db.add(ann_row)
        ref_ids = list(extract_asset_ids(mitem.type, mitem.payload))
        if ref_ids:
            await db.execute(
                update(Asset)
                .where(
                    Asset.org_id == user.org_id,
                    Asset.dataset_id == dataset_id,
                    Asset.id.in_(ref_ids),
                )
                .values(item_id=item_id)
            )
    await db.flush()
    await log_audit(
        db,
        user.id,
        user.org_id,
        "append_dataset",
        event_data={"dataset_id": str(dataset_id), "item_count": len(manifest.items)},
    )
    record_publish_success()
    return PublishResponse(
        dataset_id=dataset_id,
        status="published",
        item_count=len(manifest.items),
    )
