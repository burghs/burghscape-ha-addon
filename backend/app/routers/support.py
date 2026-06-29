"""Support ticket management."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class TicketCreate(BaseModel):
    client_id: int
    title: str
    description: Optional[str] = None
    priority: str = "normal"


SAMPLE_TICKETS = [
    {"id": 1, "client_id": 1, "title": "Add new camera integration", "hours_used": 0.5, "status": "open", "priority": "normal", "created_at": "2026-06-23T00:00:00Z"},
    {"id": 2, "client_id": 3, "title": "Dashboard redesign request", "hours_used": 1.5, "status": "in_progress", "priority": "normal", "created_at": "2026-06-22T00:00:00Z"},
    {"id": 3, "client_id": 2, "title": "Automation help for morning routine", "hours_used": 0.0, "status": "open", "priority": "low", "created_at": "2026-06-21T00:00:00Z"},
    {"id": 4, "client_id": 1, "title": "Update failed - need assistance", "hours_used": 1.0, "status": "completed", "priority": "high", "created_at": "2026-06-20T00:00:00Z"},
]


@router.get("")
async def list_tickets():
    return SAMPLE_TICKETS


@router.post("")
async def create_ticket(ticket: TicketCreate):
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/{ticket_id}/log-hours")
async def log_hours(ticket_id: int, hours: float):
    return {"ticket_id": ticket_id, "hours_logged": hours}
