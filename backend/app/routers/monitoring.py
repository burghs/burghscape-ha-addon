"""Monitoring and alert endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/alerts")
async def list_alerts():
    return [
        {"id": 1, "instance_id": 3, "alert_type": "offline", "severity": "critical", "message": "Smith Residence is offline", "is_resolved": False, "created_at": "2026-06-24T10:00:00Z"},
        {"id": 2, "instance_id": 3, "alert_type": "update_available", "severity": "info", "message": "2 updates available for Smith Residence", "is_resolved": False, "created_at": "2026-06-24T08:00:00Z"},
    ]


@router.get("/status")
async def monitoring_status():
    return {
        "monitored_instances": 4,
        "online": 3,
        "offline": 1,
        "last_check": "2026-06-24T15:00:00Z",
    }


@router.post("/check-all")
async def check_all():
    return {"status": "check_started", "instances_checked": 4}
