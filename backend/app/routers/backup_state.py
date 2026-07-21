"""Tenant-scoped managed backup operation state reporting and summaries."""
from datetime import datetime, timedelta
from typing import Literal, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Backup, BackupOperation, Client, ClientUser, HomeAssistantInstance
from routers.agent import validate_token
from routers.backups import build_backup_file_response, is_customer_backup_available, meaningful_backup_filename
from admin_auth import get_current_admin
from routers.portal_state import portal_sessions

router = APIRouter()
ACTIVE_STATES = {"creating", "downloading", "uploading"}
TERMINAL_STATES = {"completed", "failed"}
STATE_ORDER = {"creating": 0, "downloading": 1, "uploading": 2, "completed": 3, "failed": 3}
STALE_AFTER = timedelta(hours=2)

class BackupStateReport(BaseModel):
    operation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    state: Literal["creating", "downloading", "uploading", "completed", "failed"]
    automatic_enabled: bool = False
    ha_backup_slug: Optional[str] = Field(default=None, max_length=255)
    backup_id: Optional[int] = Field(default=None, ge=1)
    error_category: Optional[str] = Field(default=None, max_length=100)

def _iso(value):
    return value.isoformat() if value else None

def effective_state(operation, now=None):
    now = now or datetime.utcnow()
    if operation.state in ACTIVE_STATES and operation.updated_at and now - operation.updated_at > STALE_AFTER:
        return "stale"
    return operation.state

def serialize_operation(operation, now=None):
    if not operation:
        return None
    return {"operation_id": operation.operation_id, "state": effective_state(operation, now),
            "reported_state": operation.state, "automatic_enabled": bool(operation.automatic_enabled),
            "ha_backup_slug": operation.ha_backup_slug, "backup_id": operation.backup_id,
            "error_category": operation.error_category, "started_at": _iso(operation.started_at),
            "updated_at": _iso(operation.updated_at), "completed_at": _iso(operation.completed_at),
            "failed_at": _iso(operation.failed_at)}

async def client_backup_summary(db, client_id):
    operations = (await db.execute(select(BackupOperation).where(BackupOperation.client_id == client_id).order_by(desc(BackupOperation.updated_at)))).scalars().all()
    latest = operations[0] if operations else None
    failure = next((op for op in operations if op.state == "failed"), None)
    success = (await db.execute(select(Backup).where(Backup.client_id == client_id, Backup.status == "completed").order_by(desc(Backup.completed_at), desc(Backup.created_at)).limit(1))).scalars().first()
    return {"automatic_enabled": bool(latest.automatic_enabled) if latest else False,
            "current_operation": serialize_operation(latest),
            "last_success": ({"backup_id": success.id, "filename": success.filename, "size_bytes": success.size_bytes or 0, "completed_at": _iso(success.completed_at or success.created_at)} if success else None),
            "last_failure": serialize_operation(failure)}

def _validate_transition(existing, requested):
    if existing.state in TERMINAL_STATES and requested != existing.state:
        raise HTTPException(409, "Backup operation is already terminal")
    if STATE_ORDER[requested] < STATE_ORDER[existing.state]:
        raise HTTPException(409, "Backup state transition is out of order")

@router.post("/api/backups/state")
async def report_backup_state(report: BackupStateReport, authorization: Optional[str] = Header(None), db: AsyncSession = Depends(get_db)):
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Missing bearer token")
    client, _ = await validate_token(token, db)
    operation = (await db.execute(select(BackupOperation).where(BackupOperation.operation_id == report.operation_id))).scalars().first()
    now = datetime.utcnow()
    if operation and operation.client_id != client.id:
        raise HTTPException(409, "Operation identifier is unavailable")
    if operation:
        _validate_transition(operation, report.state)
    elif report.state != "creating":
        raise HTTPException(409, "Backup operation must begin with creating")
    else:
        operation = BackupOperation(client_id=client.id, operation_id=report.operation_id, state="creating", started_at=now)
        db.add(operation)
    if report.backup_id is not None:
        backup = (await db.execute(select(Backup).where(Backup.id == report.backup_id))).scalars().first()
        if not backup or backup.client_id != client.id:
            raise HTTPException(400, "Backup record does not belong to authenticated client")
    if report.state == "completed" and report.backup_id is None:
        raise HTTPException(400, "Completed state requires backup_id")
    operation.state, operation.automatic_enabled = report.state, report.automatic_enabled
    operation.ha_backup_slug = report.ha_backup_slug or operation.ha_backup_slug
    operation.backup_id = report.backup_id or operation.backup_id
    operation.error_category = report.error_category if report.state == "failed" else None
    operation.updated_at = now
    if report.state == "completed": operation.completed_at = now
    if report.state == "failed": operation.failed_at = now
    await db.flush()
    return serialize_operation(operation, now)

@router.get("/api/admin/managed-backup-state")
async def admin_backup_state(admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    clients = (await db.execute(select(Client).order_by(Client.name))).scalars().all()
    completed = (await db.execute(
        select(Backup).where(Backup.status == "completed").order_by(desc(Backup.completed_at), desc(Backup.created_at))
    )).scalars().all()
    instances = (await db.execute(select(HomeAssistantInstance))).scalars().all()
    instance_names = {item.client_id: item.name for item in instances}
    backups = []
    for backup in completed:
        client = next((item for item in clients if item.id == backup.client_id), None)
        if not client:
            continue
        if not await is_customer_backup_available(backup, client):
            continue
        instance_name = instance_names.get(backup.client_id) or client.name
        backups.append({
            "filename": backup.filename,
            "client_name": client.name,
            "instance_name": instance_name,
            "backup_type": "Burghscape managed backup",
            "size_bytes": backup.size_bytes or 0,
            "status": backup.status,
            "completed_at": _iso(backup.completed_at or backup.created_at),
            "download_url": f"/api/admin/managed-backups/{backup.id}/download",
        })
    return {"clients": [{"client_id": c.id, "client_name": c.name, **await client_backup_summary(db, c.id)} for c in clients], "backups": backups}

@router.get("/api/admin/managed-backups/{backup_id}/download")
async def admin_managed_backup_download(
    backup_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    backup = (await db.execute(select(Backup).where(Backup.id == backup_id))).scalars().first()
    if not backup:
        raise HTTPException(404, "Backup not found")
    client = (await db.execute(select(Client).where(Client.id == backup.client_id))).scalars().first()
    if not client:
        raise HTTPException(404, "Backup not found")
    instance = (await db.execute(select(HomeAssistantInstance).where(HomeAssistantInstance.client_id == client.id))).scalars().first()
    return await build_backup_file_response(backup, client, meaningful_backup_filename(backup, client, instance.name if instance else client.name))

@router.get("/api/portal/managed-backup-state")
async def portal_backup_state(request: Request, db: AsyncSession = Depends(get_db)):
    user_id = portal_sessions.get(request.cookies.get("portal_token", ""))
    if not user_id: raise HTTPException(401, "Portal authentication required")
    user = (await db.execute(select(ClientUser).where(ClientUser.id == user_id))).scalars().first()
    if not user or not user.is_active: raise HTTPException(401, "Portal authentication required")
    return await client_backup_summary(db, user.client_id)
