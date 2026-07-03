"""Home Assistant instance management."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class InstanceStatus(BaseModel):
    id: int
    client_id: int
    name: Optional[str]
    ha_version: Optional[str]
    is_online: bool
    ip_address: Optional[str]
    disk_usage_percent: Optional[float]
    last_backup: Optional[str]
    updates_available: List[str]
    entities_count: int
    automations_count: int


SAMPLE_INSTANCES = [
    {"id": 1, "client_id": 1, "name": "Daniel Home", "ha_version": "2026.6.0", "ip_address": "192.168.23.51", "is_online": True, "disk_usage_percent": 45.0, "last_backup": "2h ago", "updates_available": ["2026.7.1"], "entities_count": 120, "automations_count": 15},
    {"id": 2, "client_id": 1, "name": "Daniel Office", "ha_version": "2026.6.0", "ip_address": "192.168.20.50", "is_online": True, "disk_usage_percent": 32.0, "last_backup": "2h ago", "updates_available": [], "entities_count": 80, "automations_count": 8},
    {"id": 3, "client_id": 2, "name": "Smith Residence", "ha_version": "2026.5.2", "ip_address": "192.168.10.100", "is_online": False, "disk_usage_percent": 67.0, "last_backup": "3d ago", "updates_available": ["2026.6.0", "2026.7.1"], "entities_count": 45, "automations_count": 5},
    {"id": 4, "client_id": 3, "name": "Jones House", "ha_version": "2026.6.0", "ip_address": "192.168.15.20", "is_online": True, "disk_usage_percent": 28.0, "last_backup": "1h ago", "updates_available": [], "entities_count": 200, "automations_count": 32},
]


@router.get("", response_model=List[InstanceStatus])
async def list_instances():
    from routers.agent import agent_reports
    if agent_reports:
        real_instances = []
        for name, report in agent_reports.items():
            backup_data = report.get("backup", {}) or {}
            last_backup = None
            if backup_data and backup_data.get("enabled"):
                last_backup = backup_data.get("last_backup") or "configured"
            real_instances.append({
                "id": abs(hash(name)) % 10000,
                "client_id": 999,
                "name": report.get("instance_name", name),
                "ha_version": report.get("ha_version", "unknown"),
                "is_online": report.get("is_online", True),
                "ip_address": report.get("ip_address", "N/A"),
                "disk_usage_percent": report.get("disk_usage_percent"),
                "last_backup": last_backup,
                "backup_status": backup_data.get("status", "disabled") if backup_data else "disabled",
                "updates_available": report.get("updates_available", []),
                "entities_count": report.get("entities_count", 0),
                "automations_count": report.get("automations_count", 0),
            })
        if real_instances:
            return real_instances
    return SAMPLE_INSTANCES


@router.get("/{instance_id}", response_model=InstanceStatus)
async def get_instance(instance_id: int):
    inst = next((i for i in SAMPLE_INSTANCES if i["id"] == instance_id), None)
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    return inst


@router.post("/{instance_id}/check-updates")
async def check_updates(instance_id: int):
    return {"instance_id": instance_id, "updates_available": []}


@router.post("/{instance_id}/restart")
async def restart_instance(instance_id: int):
    return {"status": "restart_requested", "instance_id": instance_id}


@router.post("/{instance_id}/toggle-alerts")
async def toggle_instance_alerts(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from models import HomeAssistantInstance as HAInstance
    from routers.agent import agent_reports

    # Try direct DB lookup
    result = await db.execute(select(HAInstance).where(HAInstance.id == instance_id))
    instance = result.scalars().first()

    if not instance:
        # Try dynamic hash-based ID lookup
        for name, report in agent_reports.items():
            hash_id = abs(hash(name)) % 10000
            if hash_id == instance_id:
                inst_name = report.get("instance_name", name)
                r = await db.execute(
                    select(HAInstance).where(
                        HAInstance.name == inst_name
                    )
                )
                instance = r.scalars().first()
                if instance:
                    break

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    instance.send_alerts = not instance.send_alerts
    await db.flush()

    return {
        "instance_id": instance.id,
        "send_alerts": instance.send_alerts,
        "message": "Alerts enabled" if instance.send_alerts else "Alerts disabled"
    }