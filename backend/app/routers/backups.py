"""Backup management endpoints."""
from fastapi import APIRouter
from typing import List

router = APIRouter()

SAMPLE_BACKUPS = [
    {"id": 1, "client_id": 1, "filename": "daniel_20260624_0200.tar.gz", "size_bytes": 256901120, "status": "completed", "started_at": "2026-06-24T02:00:00Z", "completed_at": "2026-06-24T02:05:00Z"},
    {"id": 2, "client_id": 2, "filename": "smith_20260624_0200.tar.gz", "size_bytes": 188743680, "status": "completed", "started_at": "2026-06-24T02:00:00Z", "completed_at": "2026-06-24T02:04:00Z"},
    {"id": 3, "client_id": 3, "filename": "jones_20260624_0200.tar.gz", "size_bytes": 325058560, "status": "completed", "started_at": "2026-06-24T02:00:00Z", "completed_at": "2026-06-24T02:06:00Z"},
]


@router.get("")
async def list_backups():
    return SAMPLE_BACKUPS


@router.post("/{client_id}/trigger")
async def trigger_backup(client_id: int):
    return {"status": "backup_triggered", "client_id": client_id}


@router.get("/{client_id}/status")
async def backup_status(client_id: int):
    client_backups = [b for b in SAMPLE_BACKUPS if b["client_id"] == client_id]
    latest = client_backups[-1] if client_backups else None
    return {
        "client_id": client_id,
        "last_backup": latest["completed_at"] if latest else None,
        "last_backup_status": latest["status"] if latest else "none",
        "next_backup": None,
    }
