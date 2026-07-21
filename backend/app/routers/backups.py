"""Backup upload/download endpoints for tenant-scoped Home Assistant backup archives."""
from datetime import datetime
from pathlib import PurePosixPath
from typing import Optional, List
import hashlib
import logging
import os
import re
import secrets

from fastapi import APIRouter, HTTPException, Header, Depends, Query, Body, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Client, Backup, ClientStatus
from storage.factory import get_client_storage_backend
from config import get_settings


router = APIRouter()
logger = logging.getLogger("burghscape.backup")

ALLOWED_BACKUP_EXTENSIONS = (".tar", ".tar.gz", ".tgz")
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class InitiateUploadRequest(BaseModel):
    filename: str
    content_type: str = "application/gzip"
    size_bytes: Optional[int] = Field(default=None, ge=1)
    metadata: Optional[dict] = None
    checksum_sha256: Optional[str] = None


class InitiateUploadResponse(BaseModel):
    upload_id: str
    key: str
    parts: List[dict]
    max_part_size_mb: int


class CompleteUploadRequest(BaseModel):
    upload_id: str
    key: str
    parts: List[dict]
    checksum_sha256: Optional[str] = None


class CompleteUploadResponse(BaseModel):
    backup_id: int
    key: str
    size: int
    etag: str
    checksum_sha256: Optional[str] = None


class BackupListItem(BaseModel):
    id: int
    filename: str
    size_bytes: int
    storage_backend: str
    status: str
    started_at: str
    completed_at: Optional[str]


class BackupDownloadResponse(BaseModel):
    download_url: str
    expires_in: int
    filename: str


class BackupConfigResponse(BaseModel):
    max_backup_size_bytes: int
    max_part_size_bytes: int
    allowed_extensions: List[str]


def get_backup_limits() -> tuple[int, int]:
    settings = get_settings()
    max_backup_size = int(getattr(settings, "BACKUP_MAX_SIZE_BYTES", 10 * 1024 * 1024 * 1024))
    max_part_size = int(getattr(settings, "BACKUP_MAX_PART_SIZE_BYTES", 100 * 1024 * 1024))
    return max_backup_size, max_part_size


def sanitize_backup_filename(filename: str) -> str:
    raw_name = PurePosixPath(str(filename or "")).name.strip()
    if not raw_name:
        raise HTTPException(status_code=400, detail="Backup filename is required")
    safe_name = SAFE_FILENAME_RE.sub("_", raw_name).strip("._")
    if not safe_name:
        raise HTTPException(status_code=400, detail="Backup filename is invalid")
    if not safe_name.lower().endswith(ALLOWED_BACKUP_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Unsupported backup archive extension")
    return safe_name[:180]


def generate_storage_key(client_id: int, filename: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(8)
    return f"{client_id}/{timestamp}_{suffix}_{filename}"


def validate_client_storage_key(client: Client, key: str) -> str:
    if not key or key.startswith("/") or "\\" in key:
        raise HTTPException(status_code=400, detail="Invalid storage key")
    path = PurePosixPath(key)
    if ".." in path.parts or "." in path.parts:
        raise HTTPException(status_code=400, detail="Invalid storage key")
    expected_prefix = str(client.id)
    if len(path.parts) < 2 or path.parts[0] != expected_prefix:
        raise HTTPException(status_code=403, detail="Backup key does not belong to authenticated client")
    return str(path)


def validate_parts(parts: List[dict]) -> List[dict]:
    if not parts:
        raise HTTPException(status_code=400, detail="Upload parts are required")
    normalized = []
    for part in parts:
        try:
            part_number = int(part.get("part_number", part.get("PartNumber")))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid upload part number")
        etag = part.get("etag", part.get("ETag"))
        if not etag or not isinstance(etag, str):
            raise HTTPException(status_code=400, detail="Invalid upload part etag")
        if "size_bytes" in part:
            try:
                _, max_part_size = get_backup_limits()
                if int(part["size_bytes"]) > max_part_size:
                    raise HTTPException(status_code=413, detail="Upload part size exceeds configured limit")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid upload part size")
        normalized.append({"PartNumber": part_number, "ETag": etag})
    return normalized


def get_backup_storage_config() -> dict:
    settings = get_settings()
    return {
        "backend": "local",
        "path": getattr(settings, "BACKUP_LOCAL_PATH", "/backups/client-backups"),
    }


async def validate_client_token(authorization: str, db: AsyncSession) -> Client:
    """Validate Bearer token and return client."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    from models import SubscriptionToken
    token_result = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.token == token,
            SubscriptionToken.is_active == True
        )
    )
    token_obj = token_result.scalars().first()
    if not token_obj:
        logger.warning("Backup token validation failed")
        raise HTTPException(status_code=401, detail="Invalid or revoked token")

    client_result = await db.execute(select(Client).where(Client.id == token_obj.client_id))
    client = client_result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.status != ClientStatus.ACTIVE:
        raise HTTPException(status_code=403, detail=f"Client account is {client.status.value}")

    return client


@router.get("/config", response_model=BackupConfigResponse)
async def get_backup_upload_config(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Return effective upload limits for an authenticated Agent."""
    await validate_client_token(authorization, db)
    max_backup_size, max_part_size = get_backup_limits()
    return BackupConfigResponse(
        max_backup_size_bytes=max_backup_size,
        max_part_size_bytes=max_part_size,
        allowed_extensions=list(ALLOWED_BACKUP_EXTENSIONS),
    )


@router.post("/upload", response_model=InitiateUploadResponse)
async def initiate_backup_upload(
    request: InitiateUploadRequest,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Initiate a backup upload. Returns an upload ID and tenant-scoped storage key."""
    client = await validate_client_token(authorization, db)
    max_backup_size, max_part_size = get_backup_limits()
    safe_filename = sanitize_backup_filename(request.filename)
    if request.size_bytes is not None and request.size_bytes > max_backup_size:
        raise HTTPException(status_code=413, detail="Declared backup size exceeds configured limit")

    storage_config = get_backup_storage_config()
    backend = get_client_storage_backend(storage_config)
    key = generate_storage_key(client.id, safe_filename)
    metadata = dict(request.metadata or {})
    if request.checksum_sha256:
        metadata["checksum_sha256"] = request.checksum_sha256

    multipart = await backend.create_multipart_upload(
        key=key,
        content_type=request.content_type,
        metadata=metadata,
    )
    logger.info("Backup upload initiated client_id=%s", client.id)
    return InitiateUploadResponse(
        upload_id=multipart.upload_id,
        key=multipart.key,
        parts=[{"part_number": p.part_number, "upload_url": p.upload_url} for p in multipart.parts],
        max_part_size_mb=max_part_size // (1024 * 1024),
    )


@router.post("/upload/parts")
async def get_more_upload_parts(
    upload_id: str = Body(...),
    key: str = Body(...),
    start_part: int = Body(...),
    count: int = Body(100),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get additional upload part URLs for the authenticated client's upload."""
    client = await validate_client_token(authorization, db)
    key = validate_client_storage_key(client, key)
    if start_part < 1 or count < 1 or count > 100:
        raise HTTPException(status_code=400, detail="Invalid part request")
    backend = get_client_storage_backend(get_backup_storage_config())
    parts = await backend.get_more_presigned_parts(upload_id, key, start_part, count)
    return {"parts": [{"part_number": p.part_number, "upload_url": p.upload_url} for p in parts]}


@router.post("/upload/complete", response_model=CompleteUploadResponse)
async def complete_backup_upload(
    request: CompleteUploadRequest,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Complete an upload and create a backup record only after storage confirms the object exists."""
    client = await validate_client_token(authorization, db)
    key = validate_client_storage_key(client, request.key)
    parts = validate_parts(request.parts)
    backend = get_client_storage_backend(get_backup_storage_config())
    try:
        result = await backend.complete_multipart_upload(upload_id=request.upload_id, key=key, parts=parts)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail="Stored backup object was not found")
    meta = await backend.get_object_metadata(key)
    if not meta or meta.size <= 0:
        raise HTTPException(status_code=400, detail="Stored backup object was not found or is empty")
    max_backup_size, _ = get_backup_limits()
    if meta.size > max_backup_size:
        raise HTTPException(status_code=413, detail="Stored backup object exceeds configured limit")

    if request.checksum_sha256 and result.checksum and request.checksum_sha256.lower() != result.checksum.lower():
        raise HTTPException(status_code=400, detail="Backup checksum mismatch")

    backup = Backup(
        client_id=client.id,
        filename=PurePosixPath(key).name,
        size_bytes=meta.size,
        storage_backend="local",
        storage_key=key,
        storage_etag=result.etag,
        status="completed",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add(backup)
    await db.flush()
    logger.info("Backup upload completed client_id=%s backup_id=%s bytes=%s", client.id, backup.id, meta.size)
    return CompleteUploadResponse(
        backup_id=backup.id,
        key=key,
        size=meta.size,
        etag=result.etag,
        checksum_sha256=result.checksum or request.checksum_sha256,
    )



@router.post("/upload/direct", response_model=CompleteUploadResponse)
async def direct_backup_upload(
    request: Request,
    authorization: str = Header(None),
    x_backup_filename: str = Header(...),
    x_backup_size: int = Header(...),
    x_backup_sha256: str = Header(...),
    x_idempotency_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Receive one complete backup archive stream for local tenant-scoped storage."""
    client = await validate_client_token(authorization, db)
    max_backup_size, _ = get_backup_limits()
    safe_filename = sanitize_backup_filename(x_backup_filename)
    declared_size = int(x_backup_size)
    if declared_size <= 0:
        raise HTTPException(status_code=400, detail="Declared backup size must be greater than zero")
    if declared_size > max_backup_size:
        raise HTTPException(status_code=413, detail="Declared backup size exceeds configured limit")
    checksum = str(x_backup_sha256 or "").strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise HTTPException(status_code=400, detail="Invalid SHA-256 checksum")

    duplicate = await db.execute(
        select(Backup).where(
            Backup.client_id == client.id,
            Backup.filename == safe_filename,
            Backup.size_bytes == declared_size,
            Backup.storage_etag == f"sha256:{checksum}",
            Backup.status == "completed",
        )
    )
    existing = duplicate.scalars().first()
    if existing:
        logger.info("Backup direct upload idempotent hit client_id=%s backup_id=%s", client.id, existing.id)
        return CompleteUploadResponse(
            backup_id=existing.id,
            key=existing.storage_key,
            size=existing.size_bytes or 0,
            etag=existing.storage_etag or "",
            checksum_sha256=checksum,
        )

    backend = get_client_storage_backend(get_backup_storage_config())
    key = generate_storage_key(client.id, safe_filename)
    key = validate_client_storage_key(client, key)
    final_path = backend._full_path(key)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    operation_id = secrets.token_hex(8)
    temp_path = final_path.parent / f".{final_path.name}.{operation_id}.tmp"
    hasher = hashlib.sha256()
    received = 0
    stored = False
    recorded = False

    try:
        with open(temp_path, "wb") as f:
            async for chunk in request.stream():
                if not chunk:
                    continue
                received += len(chunk)
                if received > max_backup_size:
                    raise HTTPException(status_code=413, detail="Uploaded backup exceeds configured limit")
                if received > declared_size:
                    raise HTTPException(status_code=400, detail="Uploaded backup exceeds declared size")
                hasher.update(chunk)
                f.write(chunk)
        if received == 0:
            raise HTTPException(status_code=400, detail="Uploaded backup is empty")
        if received != declared_size:
            raise HTTPException(status_code=400, detail="Uploaded backup size does not match declaration")
        actual_checksum = hasher.hexdigest()
        if actual_checksum != checksum:
            raise HTTPException(status_code=400, detail="Backup checksum mismatch")
        os.replace(temp_path, final_path)
        stored = True

        meta = await backend.get_object_metadata(key)
        if not meta or meta.size != declared_size or meta.size <= 0:
            raise HTTPException(status_code=400, detail="Stored backup object failed verification")

        backup = Backup(
            client_id=client.id,
            filename=safe_filename,
            size_bytes=declared_size,
            storage_backend="local",
            storage_key=key,
            storage_etag=f"sha256:{actual_checksum}",
            status="completed",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(backup)
        await db.flush()
        await db.commit()
        recorded = True
        logger.info(
            "Backup direct upload completed client_id=%s backup_id=%s bytes=%s operation_id=%s",
            client.id,
            backup.id,
            declared_size,
            operation_id,
        )
        return CompleteUploadResponse(
            backup_id=backup.id,
            key=key,
            size=declared_size,
            etag=backup.storage_etag,
            checksum_sha256=actual_checksum,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Backup direct upload failed client_id=%s operation_id=%s error=%s", client.id, operation_id, type(e).__name__)
        raise HTTPException(status_code=500, detail="Backup upload failed")
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        if stored and not recorded and final_path.exists():
            try:
                final_path.unlink()
            except OSError:
                pass


@router.post("/upload/abort")
async def abort_backup_upload(
    upload_id: str = Body(...),
    key: str = Body(...),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Abort an upload for the authenticated client."""
    client = await validate_client_token(authorization, db)
    key = validate_client_storage_key(client, key)
    backend = get_client_storage_backend(get_backup_storage_config())
    await backend.abort_multipart_upload(upload_id, key)
    logger.info("Backup upload aborted client_id=%s", client.id)
    return {"status": "aborted"}


@router.get("/list", response_model=List[BackupListItem])
async def list_backups(
    limit: int = Query(50, ge=1, le=200),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """List backups for the authenticated client."""
    client = await validate_client_token(authorization, db)
    result = await db.execute(
        select(Backup)
        .where(Backup.client_id == client.id)
        .order_by(desc(Backup.created_at))
        .limit(limit)
    )
    backups = result.scalars().all()
    return [
        BackupListItem(
            id=b.id,
            filename=b.filename,
            size_bytes=b.size_bytes or 0,
            storage_backend=b.storage_backend,
            status=b.status,
            started_at=b.started_at.isoformat() if b.started_at else "",
            completed_at=b.completed_at.isoformat() if b.completed_at else None,
        )
        for b in backups
    ]


@router.get("/download/{backup_id}", response_model=BackupDownloadResponse)
async def get_backup_download_url(
    backup_id: int,
    expires_in: int = Query(3600, ge=60, le=86400),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Get a download URL for a backup owned by the authenticated client."""
    client = await validate_client_token(authorization, db)
    result = await db.execute(select(Backup).where(Backup.id == backup_id, Backup.client_id == client.id))
    backup = result.scalars().first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    if backup.status != "completed":
        raise HTTPException(status_code=400, detail="Backup not ready")
    key = validate_client_storage_key(client, backup.storage_key)
    return BackupDownloadResponse(
        download_url=f"/api/backups/download-file/{backup.id}",
        expires_in=expires_in,
        filename=backup.filename,
    )


async def build_backup_file_response(backup: Backup, client: Client):
    """Build an authenticated download response through the configured storage backend."""
    if backup.status != "completed":
        raise HTTPException(status_code=400, detail="Backup not ready")
    key = validate_client_storage_key(client, backup.storage_key)
    backend = get_client_storage_backend(get_backup_storage_config())
    metadata = await backend.get_object_metadata(key)
    if not metadata or metadata.size <= 0:
        raise HTTPException(status_code=404, detail="Backup object not found")
    filename = sanitize_backup_filename(backup.filename or PurePosixPath(key).name)
    media_type = "application/gzip" if filename.lower().endswith((".tar.gz", ".tgz")) else "application/x-tar"
    if hasattr(backend, "_full_path"):
        path = backend._full_path(key)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Backup object not found")
        return FileResponse(path, media_type=media_type, filename=filename)
    download_url = await backend.generate_presigned_download_url(key, expires_in=300, filename=filename)
    return RedirectResponse(download_url, status_code=302)


@router.get("/download-file/{backup_id}")
async def download_backup_file(
    backup_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Stream a local backup file owned by the authenticated client."""
    client = await validate_client_token(authorization, db)
    result = await db.execute(select(Backup).where(Backup.id == backup_id, Backup.client_id == client.id))
    backup = result.scalars().first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    return await build_backup_file_response(backup, client)


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Delete a backup owned by the authenticated client from storage and database."""
    client = await validate_client_token(authorization, db)
    result = await db.execute(select(Backup).where(Backup.id == backup_id, Backup.client_id == client.id))
    backup = result.scalars().first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    key = validate_client_storage_key(client, backup.storage_key)
    backend = get_client_storage_backend(get_backup_storage_config())
    await backend.delete_object(key)
    await db.delete(backup)
    logger.info("Backup deleted client_id=%s backup_id=%s", client.id, backup_id)
    return {"status": "deleted"}
