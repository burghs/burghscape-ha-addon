"""Support ticket management."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database import get_db
from models import SupportTicket
from datetime import datetime

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


@router.get("")
async def list_tickets(db: AsyncSession = Depends(get_db)):
    """List all support tickets from database."""
    result = await db.execute(
        select(SupportTicket).order_by(SupportTicket.created_at.desc())
    )
    tickets = result.scalars().all()
    return [
        {
            "id": t.id,
            "client_id": t.client_id,
            "title": t.title,
            "description": t.description,
            "hours_used": t.hours_used or 0,
            "status": t.status or "open",
            "priority": t.priority or "normal",
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in tickets
    ]


@router.post("")
async def create_ticket(ticket: TicketCreate, db: AsyncSession = Depends(get_db)):
    """Create a new support ticket."""
    new_ticket = SupportTicket(
        client_id=ticket.client_id,
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        status="open",
        hours_used=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_ticket)
    await db.commit()
    await db.refresh(new_ticket)
    return {
        "id": new_ticket.id,
        "client_id": new_ticket.client_id,
        "title": new_ticket.title,
        "status": new_ticket.status,
    }


@router.put("/{ticket_id}")
async def update_ticket(ticket_id: int, update: TicketUpdate, db: AsyncSession = Depends(get_db)):
    """Update a support ticket."""
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(ticket, key, value)
    ticket.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(ticket)
    return {"id": ticket.id, "title": ticket.title, "status": ticket.status}


@router.delete("/{ticket_id}")
async def delete_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a support ticket."""
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    await db.execute(delete(SupportTicket).where(SupportTicket.id == ticket_id))
    await db.commit()
    return {"message": "Ticket deleted"}


@router.post("/{ticket_id}/log-hours")
async def log_hours(ticket_id: int, hours: float, db: AsyncSession = Depends(get_db)):
    """Log hours against a support ticket."""
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    ticket.hours_used = (ticket.hours_used or 0) + hours
    ticket.updated_at = datetime.utcnow()
    
    await db.commit()
    return {"ticket_id": ticket_id, "hours_logged": hours, "total_hours": ticket.hours_used}
