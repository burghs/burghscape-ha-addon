"""Home Assistant instance management."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Backup, BackupOperation, Client, HomeAssistantInstance
from routers.backups import is_customer_backup_available
router = APIRouter()

class InstanceStatus(BaseModel):
    id: int
    client_id: int
    client_name: Optional[str] = None
    name: Optional[str] = None
    ha_version: Optional[str] = None
    agent_version: Optional[str] = None
    is_online: bool
    ip_address: Optional[str] = None
    tunnel_status: Optional[str] = None
    disk_usage_percent: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    memory_usage_percent: Optional[float] = None
    database_size: Optional[str] = None
    last_seen: Optional[str] = None
    last_successful_managed_backup: Optional[str] = None
    managed_backup_status: Optional[str] = None
    updates_available: List[str] = []
    entities_count: int = 0
    automations_count: int = 0

def _agent_version(report):
    for addon in report.get("addons") or []:
        if isinstance(addon, dict) and any(word in " ".join(str(addon.get(k, "")) for k in ("slug", "name")).lower() for word in ("burghscape", "mybeacon")):
            return addon.get("version")
    return report.get("addon_version")

@router.get("", response_model=List[InstanceStatus])
async def list_instances(db: AsyncSession = Depends(get_db)):
    from routers.agent import agent_reports
    instances = (await db.execute(select(HomeAssistantInstance).order_by(HomeAssistantInstance.name))).scalars().all()
    clients = (await db.execute(select(Client))).scalars().all()
    client_names = {client.id: client.name for client in clients}
    client_by_id = {client.id: client for client in clients}
    tunnel_clients = {client.id for client in clients if client.cloudflare_tunnel_id}
    completed = (await db.execute(select(Backup).where(Backup.status == "completed").order_by(desc(Backup.completed_at), desc(Backup.created_at)))).scalars().all()
    latest_backups = {}
    for backup in completed:
        client = client_by_id.get(backup.client_id)
        if client and backup.client_id not in latest_backups and await is_customer_backup_available(backup, client):
            latest_backups[backup.client_id] = backup
    operations = (await db.execute(select(BackupOperation).order_by(desc(BackupOperation.updated_at)))).scalars().all()
    latest_operations = {}
    for operation in operations: latest_operations.setdefault(operation.client_id, operation)
    reports = {report.get("client_id"): report for report in agent_reports.values() if report.get("client_id") is not None}
    response = []
    for instance in instances:
        report = reports.get(instance.client_id, {})
        ip = report.get("ip_address")
        if ip in ("0.0.0.0", "N/A", "unknown"): ip = None
        latest = latest_backups.get(instance.client_id)
        operation = latest_operations.get(instance.client_id)
        tailscale = report.get("tailscale") or {}
        response.append({"id": instance.id, "client_id": instance.client_id, "client_name": client_names.get(instance.client_id),
            "name": instance.name, "ha_version": report.get("ha_version") or instance.ha_version,
            "agent_version": _agent_version(report), "is_online": bool(report.get("is_online", instance.is_online)),
            "ip_address": ip, "tunnel_status": tailscale.get("status") or ("Configured" if instance.client_id in tunnel_clients else None),
            "disk_usage_percent": report.get("disk_usage_percent", instance.disk_usage_percent),
            "cpu_usage_percent": report.get("cpu_usage_percent", instance.cpu_usage_percent),
            "memory_usage_percent": report.get("memory_usage_percent", instance.memory_usage_percent),
            "database_size": (report.get("backup_status") or {}).get("database_size"),
            "last_seen": report.get("last_seen") or (instance.last_seen.isoformat() if instance.last_seen else None),
            "last_successful_managed_backup": ((latest.completed_at or latest.created_at).isoformat() if latest and (latest.completed_at or latest.created_at) else None),
            "managed_backup_status": operation.state if operation else ("completed" if latest else None),
            "updates_available": report.get("updates_available") or instance.updates_available or [],
            "entities_count": report.get("entities_count", instance.entities_count or 0),
            "automations_count": report.get("automations_count", instance.automations_count or 0)})
    return response

@router.get("/{instance_id}", response_model=InstanceStatus)
async def get_instance(instance_id: int, db: AsyncSession = Depends(get_db)):
    instance = next((item for item in await list_instances(db) if item["id"] == instance_id), None)
    if not instance: raise HTTPException(404, "Instance not found")
    return instance

@router.post("/{instance_id}/check-updates")
async def check_updates(instance_id: int):
    return {"instance_id": instance_id, "updates_available": []}

@router.post("/{instance_id}/restart")
async def restart_instance(instance_id: int):
    return {"status": "restart_requested", "instance_id": instance_id}

@router.post("/{instance_id}/toggle-alerts")
async def toggle_instance_alerts(instance_id: int, db: AsyncSession = Depends(get_db)):
    instance = (await db.execute(select(HomeAssistantInstance).where(HomeAssistantInstance.id == instance_id))).scalars().first()
    if not instance: raise HTTPException(404, "Instance not found")
    instance.send_alerts = not instance.send_alerts; await db.flush()
    return {"instance_id": instance.id, "send_alerts": instance.send_alerts,
        "message": "Alerts enabled" if instance.send_alerts else "Alerts disabled"}
