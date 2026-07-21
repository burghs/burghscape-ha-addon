"""Support ticket management."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database import get_db
from models import Client, SupportTicket
from support_hours import calculate_support_hours, format_hours
router = APIRouter()

class TicketCreate(BaseModel):
    client_id: int
    title: str
    description: Optional[str] = None
    priority: str = "normal"

class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    hours_used: Optional[float] = None
    resolution: Optional[str] = None

def serialize_ticket(ticket, client_name=None):
    return {"id": ticket.id, "client_id": ticket.client_id, "client_name": client_name or f"Client #{ticket.client_id}",
        "title": ticket.title, "description": ticket.description, "resolution": ticket.resolution,
        "hours_used": ticket.hours_used or 0, "status": ticket.status or "open", "priority": ticket.priority or "normal",
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "completed_at": ticket.completed_at.isoformat() if ticket.completed_at else None}

@router.get("")
async def list_tickets(db: AsyncSession = Depends(get_db)):
    tickets = (await db.execute(select(SupportTicket).order_by(SupportTicket.created_at.desc()))).scalars().all()
    ids = {ticket.client_id for ticket in tickets}
    clients = (await db.execute(select(Client).where(Client.id.in_(ids)))).scalars().all() if ids else []
    names = {client.id: client.name for client in clients}
    return [serialize_ticket(ticket, names.get(ticket.client_id)) for ticket in tickets]

@router.get("/hours-summary")
async def support_hours_summary(db: AsyncSession = Depends(get_db)):
    clients = (await db.execute(select(Client).order_by(Client.name))).scalars().all()
    tickets = (await db.execute(select(SupportTicket))).scalars().all()
    ticket_hours = {}
    for ticket in tickets:
        ticket_hours.setdefault(ticket.client_id, []).append(ticket.hours_used or 0)
    summaries = {}
    for client in clients:
        values = calculate_support_hours(client.monthly_hours_included, ticket_hours.get(client.id, []))
        summaries[str(client.id)] = {"tier": client.tier.value if hasattr(client.tier, "value") else str(client.tier),
            **{key: format_hours(value) for key, value in values.items()}}
    return {"clients": summaries}

@router.post("")
async def create_ticket(ticket: TicketCreate, db: AsyncSession = Depends(get_db)):
    item = SupportTicket(client_id=ticket.client_id, title=ticket.title, description=ticket.description,
        priority=ticket.priority, status="open", hours_used=0, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(item); await db.commit(); await db.refresh(item)
    return serialize_ticket(item)

@router.put("/{ticket_id}")
async def update_ticket(ticket_id: int, update: TicketUpdate, db: AsyncSession = Depends(get_db)):
    ticket = (await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))).scalar_one_or_none()
    if not ticket: raise HTTPException(404, "Ticket not found")
    data = update.model_dump(exclude_unset=True)
    if data.get("hours_used") is not None and data["hours_used"] < 0: raise HTTPException(400, "Hours used cannot be negative")
    if data.get("status") in ("closed", "completed") and ticket.status not in ("closed", "completed"):
        ticket.completed_at = datetime.utcnow()
    for key, value in data.items(): setattr(ticket, key, value)
    ticket.updated_at = datetime.utcnow()
    await db.commit(); await db.refresh(ticket)
    client = (await db.execute(select(Client).where(Client.id == ticket.client_id))).scalar_one_or_none()
    return serialize_ticket(ticket, client.name if client else None)

@router.delete("/{ticket_id}")
async def delete_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)):
    ticket = (await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))).scalar_one_or_none()
    if not ticket: raise HTTPException(404, "Ticket not found")
    await db.execute(delete(SupportTicket).where(SupportTicket.id == ticket_id)); await db.commit()
    return {"message": "Ticket deleted"}

@router.post("/{ticket_id}/log-hours")
async def log_hours(ticket_id: int, hours: float, db: AsyncSession = Depends(get_db)):
    if hours < 0: raise HTTPException(400, "Hours cannot be negative")
    ticket = (await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))).scalar_one_or_none()
    if not ticket: raise HTTPException(404, "Ticket not found")
    ticket.hours_used = (ticket.hours_used or 0) + hours; ticket.updated_at = datetime.utcnow()
    await db.commit()
    return {"ticket_id": ticket_id, "hours_logged": hours, "total_hours": ticket.hours_used}
