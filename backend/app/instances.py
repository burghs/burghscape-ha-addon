"""Home Assistant instance management."""
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
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


def _is_stale(last_seen_str: str, threshold_minutes: int = 5) -> bool:
    """Check if a heartbeat timestamp is stale (older than threshold)."""
    if not last_seen_str:
        return True
    try:
        # Handle both ISO formats
        if last_seen_str.endswith("Z"):
            last_seen_str = last_seen_str.replace("Z", "+00:00")
        last_seen = datetime.fromisoformat(last_seen_str)
        now = datetime.now(last_seen.tzinfo) if last_seen.tzinfo else datetime.utcnow()
        return (now - last_seen) > timedelta(minutes=threshold_minutes)
    except (ValueError, TypeError):
        return True


@router.get("", response_model=List[InstanceStatus])
async def list_instances():
    from routers.agent import agent_reports
    if agent_reports:
        real_instances = []
        now_utc = datetime.utcnow()
        for name, report in agent_reports.items():
            last_seen = report.get("last_seen", "")
            # Mark offline if no heartbeat in last 5 minutes
            is_online = report.get("is_online", True) and not _is_stale(last_seen, 5)
            real_instances.append({
                "id": abs(hash(name)) % 10000,
                "client_id": report.get("client_id", 999),
                "name": report.get("instance_name", name),
                "ha_version": report.get("ha_version", "unknown"),
                "is_online": is_online,
                "ip_address": report.get("ip_address", "N/A"),
                "disk_usage_percent": report.get("disk_usage_percent"),
                "last_backup": report.get("last_backup"),
                "updates_available": report.get("updates_available", []),
                "entities_count": report.get("entities_count", 0),
                "automations_count": report.get("automations_count", 0),
            })
        if real_instances:
            return real_instances
    return SAMPLE_INSTANCES


@router.get("/{instance_id}", response_model=InstanceStatus)
async def get_instance(instance_id: int):
    from routers.agent import agent_reports
    for name, report in agent_reports.items():
        if abs(hash(name)) % 10000 == instance_id:
            last_seen = report.get("last_seen", "")
            is_online = report.get("is_online", True) and not _is_stale(last_seen, 5)
            return {
                "id": abs(hash(name)) % 10000,
                "client_id": report.get("client_id", 999),
                "name": report.get("instance_name", name),
                "ha_version": report.get("ha_version", "unknown"),
                "is_online": is_online,
                "ip_address": report.get("ip_address", "N/A"),
                "disk_usage_percent": report.get("disk_usage_percent"),
                "last_backup": report.get("last_backup"),
                "updates_available": report.get("updates_available", []),
                "entities_count": report.get("entities_count", 0),
                "automations_count": report.get("automations_count", 0),
            }
    # Fallback to sample data
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
