"""Backup upload/download endpoints using multipart upload to R2/S3."""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Header, Depends, Query, Body
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Client, Backup, HomeAssistantInstance, BackupStorageBackend
from storage.factory import get_client_storage_backend
from config import get_settings


router = APIRouter()


class InitiateUploadRequest(BaseModel):
    filename: str
    content_type: str = "application/gzip"
    metadata: Optional[dict] = None


class InitiateUploadResponse(BaseModel):
    upload_id: str
    key: str
    parts: List[dict]  # [{"part_number": 1, "upload_url": "..."}, ...]
    max_part_size_mb: int = 100


class CompleteUploadRequest(BaseModel):
    upload_id: str
    key: str
    parts: List[dict]  # [{"part_number": 1, "etag": "..."}, ...]


class CompleteUploadResponse(BaseModel):
    backup_id: int
    key: str
    size: int
    etag: str


class BackupListItem(BaseModel):
    id: int
    filename: str
    size_bytes: int
    storage_backend: str
    storage_key: str
    status: str
    started_at: str
    completed_at: Optional[str]


class BackupDownloadResponse(BaseModel):
    download_url: str
    expires_in: int
    filename: str


async def validate_client_token(
    authorization: str, 
    db: AsyncSession
) -> Client:
    """Validate Bearer token and return client."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.replace("Bearer ", "")
    
    import logging
    logging.getLogger("burghscape.backup").info("Validating token: len=%s, prefix=%s, is_active check", 
        len(token), token[:16])
    # Actually validate via subscription token
    from models import SubscriptionToken
    token_result = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.token == token,
            SubscriptionToken.is_active == True
        )
    )
    token_obj = token_result.scalars().first()
    if token_obj:
        logging.getLogger("burghscape.backup").info("Token found: client_id=%s", token_obj.client_id)
    else:
        logging.getLogger("burghscape.backup").warning("Token NOT found in DB!")
    if not token_obj:
        raise HTTPException(status_code=401, detail="Invalid or revoked token")
    
    client_result = await db.execute(
        select(Client).where(Client.id == token_obj.client_id)
    )
    client = client_result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.status.value != "active":
        raise HTTPException(status_code=403, detail=f"Client account is {client.status.value}")
    
    return client


@router.post("/upload", response_model=InitiateUploadResponse)
async def initiate_backup_upload(
    request: InitiateUploadRequest,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Initiate a multipart backup upload. Returns upload_id and presigned part URLs."""
    client = await validate_client_token(authorization, db)
    
    # Get storage backend for this client
    storage_config = {
        "backend": client.backup_storage_backend.value if client.backup_storage_backend else "r2",
        ** (client.backup_storage_config or {}),
    }
    
    # Add R2 credentials from settings
    settings = get_settings()
    if storage_config["backend"] == "r2":
        storage_config.update({
            "account_id": settings.R2_ACCOUNT_ID,
            "access_key_id": settings.R2_ACCESS_KEY_ID,
            "secret_access_key": settings.R2_SECRET_ACCESS_KEY,
            "bucket": settings.R2_BUCKET,
        })
    
    backend = get_client_storage_backend(storage_config)
    
    # Generate storage key: client_id/timestamp_filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    key = f"{client.id}/{timestamp}_{request.filename}"
    
    multipart = await backend.create_multipart_upload(
        key=key,
        content_type=request.content_type,
        metadata=request.metadata or {},
    )
    
    # Convert parts to dict format
    parts = [
        {"part_number": p.part_number, "upload_url": p.upload_url}
        for p in multipart.parts
    ]
    
    return InitiateUploadResponse(
        upload_id=multipart.upload_id,
        key=multipart.key,
        parts=parts,
        max_part_size_mb=100,
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
    """Get more presigned part URLs for large uploads (>100 parts)."""
    client = await validate_client_token(authorization, db)
    
    storage_config = {
        "backend": client.backup_storage_backend.value if client.backup_storage_backend else "r2",
        ** (client.backup_storage_config or {}),
    }
    settings = get_settings()
    if storage_config["backend"] == "r2":
        storage_config.update({
            "account_id": settings.R2_ACCOUNT_ID,
            "access_key_id": settings.R2_ACCESS_KEY_ID,
            "secret_access_key": settings.R2_SECRET_ACCESS_KEY,
            "bucket": settings.R2_BUCKET,
        })
    
    backend = get_client_storage_backend(storage_config)
    
    if not hasattr(backend, "get_more_presigned_parts"):
        raise HTTPException(status_code=501, detail="Not supported by this backend")
    
    parts = await backend.get_more_presigned_parts(upload_id, key, start_part, count)
    return {"parts": [{"part_number": p.part_number, "upload_url": p.upload_url} for p in parts]}


@router.post("/upload/complete", response_model=CompleteUploadResponse)
async def complete_backup_upload(
    request: CompleteUploadRequest,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Complete a multipart upload and create backup record."""
    client = await validate_client_token(authorization, db)
    
    storage_config = {
        "backend": client.backup_storage_backend.value if client.backup_storage_backend else "r2",
        ** (client.backup_storage_config or {}),
    }
    settings = get_settings()
    if storage_config["backend"] == "r2":
        storage_config.update({
            "account_id": settings.R2_ACCOUNT_ID,
            "access_key_id": settings.R2_ACCESS_KEY_ID,
            "secret_access_key": settings.R2_SECRET_ACCESS_KEY,
            "bucket": settings.R2_BUCKET,
        })
    
    backend = get_client_storage_backend(storage_config)
    
    # Complete the multipart upload
    result = await backend.complete_multipart_upload(
        upload_id=request.upload_id,
        key=request.key,
        parts=request.parts,
    )
    
    # Get actual size from object metadata
    meta = await backend.get_object_metadata(request.key)
    size = meta.size if meta else 0
    
    # Create backup record in DB
    backup = Backup(
        client_id=client.id,
        filename=request.key.split("/")[-1],
        size_bytes=size,
        storage_backend=client.backup_storage_backend.value if client.backup_storage_backend else "r2",
        storage_key=request.key,
        storage_etag=result.etag,
        status="completed",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db.add(backup)
    await db.flush()
    
    return CompleteUploadResponse(
        backup_id=backup.id,
        key=request.key,
        size=size,
        etag=result.etag,
    )


@router.post("/upload/abort")
async def abort_backup_upload(
    upload_id: str = Body(...),
    key: str = Body(...),
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Abort a multipart upload."""
    client = await validate_client_token(authorization, db)
    
    storage_config = {
        "backend": client.backup_storage_backend.value if client.backup_storage_backend else "r2",
        ** (client.backup_storage_config or {}),
    }
    settings = get_settings()
    if storage_config["backend"] == "r2":
        storage_config.update({
            "account_id": settings.R2_ACCOUNT_ID,
            "access_key_id": settings.R2_ACCESS_KEY_ID,
            "secret_access_key": settings.R2_SECRET_ACCESS_KEY,
            "bucket": settings.R2_BUCKET,
        })
    
    backend = get_client_storage_backend(storage_config)
    
    await backend.abort_multipart_upload(upload_id, key)
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
            storage_key=b.storage_key,
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
    """Get a presigned download URL for a backup."""
    client = await validate_client_token(authorization, db)
    
    result = await db.execute(
        select(Backup).where(
            Backup.id == backup_id,
            Backup.client_id == client.id
        )
    )
    backup = result.scalars().first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    storage_config = {
        "backend": backup.storage_backend,
        ** (client.backup_storage_config or {}),
    }
    settings = get_settings()
    if storage_config["backend"] == "r2":
        storage_config.update({
            "account_id": settings.R2_ACCOUNT_ID,
            "access_key_id": settings.R2_ACCESS_KEY_ID,
            "secret_access_key": settings.R2_SECRET_ACCESS_KEY,
            "bucket": settings.R2_BUCKET,
        })
    
    backend = get_client_storage_backend(storage_config)
    
    download_url = await backend.generate_presigned_download_url(
        key=backup.storage_key,
        expires_in=expires_in,
        filename=backup.filename,
    )
    
    return BackupDownloadResponse(
        download_url=download_url,
        expires_in=expires_in,
        filename=backup.filename,
    )


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: int,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Delete a backup from storage and database."""
    client = await validate_client_token(authorization, db)
    
    result = await db.execute(
        select(Backup).where(
            Backup.id == backup_id,
            Backup.client_id == client.id
        )
    )
    backup = result.scalars().first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    
    storage_config = {
        "backend": backup.storage_backend,
        ** (client.backup_storage_config or {}),
    }
    settings = get_settings()
    if storage_config["backend"] == "r2":
        storage_config.update({
            "account_id": settings.R2_ACCOUNT_ID,
            "access_key_id": settings.R2_ACCESS_KEY_ID,
            "secret_access_key": settings.R2_SECRET_ACCESS_KEY,
            "bucket": settings.R2_BUCKET,
        })
    
    backend = get_client_storage_backend(storage_config)
    
    await backend.delete_object(backup.storage_key)
    await db.delete(backup)
    
    return {"status": "deleted"}

