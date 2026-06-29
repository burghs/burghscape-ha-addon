"""Client and subscription management endpoints."""
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Client, SubscriptionToken, HomeAssistantInstance, SubscriptionTier, ClientStatus, SupportTicket, ClientUser

router = APIRouter()


# --- Pydantic Schemas ---

class ClientCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    subdomain: str
    tier: str = "basic"
    monthly_hours_included: int = 0

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    subdomain: Optional[str] = None
    tier: Optional[str] = None
    status: Optional[str] = None
    monthly_hours_included: Optional[int] = None

class TokenCreate(BaseModel):
    expires_days: int = 365
    notes: Optional[str] = None

class TokenResponse(BaseModel):
    id: int
    token: str
    is_active: bool
    created_at: str
    expires_at: Optional[str]
    last_used: Optional[str]

class ClientResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    subdomain: str
    tier: str
    status: str
    monthly_hours_included: int
    hours_used_this_month: float
    hours_remaining: float
    portal_url: str
    cloudflare_tunnel_id: Optional[str]
    cloudflare_tunnel_token: Optional[str]
    created_at: Optional[str]
    active_token: Optional[str] = None
    instance_count: int = 0
    is_online: bool = False


# --- Helper Functions ---

def create_token() -> str:
    """Generate a secure 32-character hex token."""
    return secrets.token_hex(32)

def client_to_dict(client: Client, token: Optional[str] = None, instance_count: int = 0, is_online: bool = False) -> dict:
    return {
        "id": client.id,
        "name": client.name,
        "email": client.email,
        "phone": client.phone,
        "subdomain": client.subdomain,
        "tier": client.tier.value if hasattr(client.tier, 'value') else client.tier,
        "status": client.status.value if hasattr(client.status, 'value') else client.status,
        "monthly_hours_included": client.monthly_hours_included,
        "hours_used_this_month": client.hours_used_this_month,
        "hours_remaining": max(0, client.monthly_hours_included - client.hours_used_this_month),
        "portal_url": f"https://{client.subdomain}.mybeacon.co.za",
        "cloudflare_tunnel_id": client.cloudflare_tunnel_id,
        "cloudflare_tunnel_token": client.cloudflare_tunnel_token,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "active_token": token,
        "instance_count": instance_count,
        "is_online": is_online,
    }


# --- Endpoints ---

@router.get("", response_model=List[ClientResponse])
async def list_clients(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).order_by(Client.created_at.desc()))
    clients = result.scalars().all()
    
    response = []
    for client in clients:
        # Get active token for each client
        token_result = await db.execute(
            select(SubscriptionToken).where(
                SubscriptionToken.client_id == client.id,
                SubscriptionToken.is_active == True
            ).order_by(SubscriptionToken.created_at.desc())
        )
        active_token = token_result.scalars().first()
        token_str = active_token.token if active_token else None
        
        # Get instance info
        inst_result = await db.execute(
            select(HomeAssistantInstance).where(
                HomeAssistantInstance.client_id == client.id
            )
        )
        instances = inst_result.scalars().all()
        instance_count = len(instances)
        is_online = any(inst.is_online for inst in instances)
        
        response.append(client_to_dict(client, token_str, instance_count, is_online))
    
    return response


@router.post("", response_model=ClientResponse)
async def create_client(client_data: ClientCreate, db: AsyncSession = Depends(get_db)):
    # Validate tier
    try:
        tier = SubscriptionTier(client_data.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {client_data.tier}. Must be: basic, standard, premium")
    
    # Set hours based on tier
    hours_map = {"basic": 0, "standard": 2, "premium": 5}
    hours = hours_map.get(client_data.tier, 0)
    if client_data.monthly_hours_included:
        hours = client_data.monthly_hours_included
    
    # Create client
    client = Client(
        name=client_data.name,
        email=client_data.email,
        phone=client_data.phone,
        subdomain=client_data.subdomain.lower().replace(" ", "-"),
        tier=tier,
        status=ClientStatus.ACTIVE,
        monthly_hours_included=hours,
    )
    db.add(client)
    await db.flush()
    
    # Auto-generate token for new client
    token = SubscriptionToken(
        client_id=client.id,
        token=create_token(),
        is_active=True,
        expires_at=datetime.now() + timedelta(days=365),
    )
    db.add(token)
    await db.flush()
    
    # Auto-create portal user for the client
    from routers.portal_users import hash_password
    from email_service import generate_temp_password, send_welcome_email
    
    temp_password = generate_temp_password(10)
    
    portal_user = ClientUser(
        client_id=client.id,
        name=client.name,
        email=client.email,
        password_hash=hash_password(temp_password),
        role="admin",  # Client admin can manage their own users
        force_password_change=True,
    )
    db.add(portal_user)
    await db.flush()
    
    # Send welcome email
    portal_url = f"https://{client.subdomain}.mybeacon.co.za"
    send_welcome_email(
        to_email=client.email,
        client_name=client.name,
        temp_password=temp_password,
        portal_url=portal_url,
    )
    
    return client_to_dict(client, token.token)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get active token
    token_result = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.client_id == client.id,
            SubscriptionToken.is_active == True
        ).order_by(SubscriptionToken.created_at.desc())
    )
    active_token = token_result.scalars().first()
    token_str = active_token.token if active_token else None
    
    return client_to_dict(client, token_str)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(client_id: int, client_data: ClientUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = client_data.model_dump(exclude_unset=True)
    
    # Validate tier if provided
    if "tier" in update_data:
        try:
            tier = SubscriptionTier(update_data["tier"])
            update_data["tier"] = tier
            # Reset hours when tier changes
            hours_map = {"basic": 0, "standard": 2, "premium": 5}
            if "monthly_hours_included" not in update_data:
                update_data["monthly_hours_included"] = hours_map.get(update_data["tier"].value, 0)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid tier: {update_data['tier']}")
    
    # Validate status if provided
    if "status" in update_data:
        try:
            status = ClientStatus(update_data["status"])
            update_data["status"] = status
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update_data['status']}")
    
    for key, value in update_data.items():
        setattr(client, key, value)
    
    await db.flush()
    
    # Get active token
    token_result = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.client_id == client.id,
            SubscriptionToken.is_active == True
        ).order_by(SubscriptionToken.created_at.desc())
    )
    active_token = token_result.scalars().first()
    token_str = active_token.token if active_token else None
    
    return client_to_dict(client, token_str)


@router.delete("/{client_id}")
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    await db.delete(client)
    return {"status": "deleted", "client_id": client_id}


# --- Token Management Endpoints ---

@router.post("/{client_id}/tokens", response_model=TokenResponse)
async def generate_token(client_id: int, token_data: TokenCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Deactivate old tokens
    old_tokens = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.client_id == client_id,
            SubscriptionToken.is_active == True
        )
    )
    for old_token in old_tokens.scalars().all():
        old_token.is_active = False
    
    # Create new token
    new_token = SubscriptionToken(
        client_id=client_id,
        token=create_token(),
        is_active=True,
        expires_at=datetime.now() + timedelta(days=token_data.expires_days),
    )
    db.add(new_token)
    await db.flush()
    
    return TokenResponse(
        id=new_token.id,
        token=new_token.token,
        is_active=new_token.is_active,
        created_at=new_token.created_at.isoformat() if new_token.created_at else None,
        expires_at=new_token.expires_at.isoformat() if new_token.expires_at else None,
        last_used=new_token.last_used.isoformat() if new_token.last_used else None,
    )


@router.get("/{client_id}/tokens", response_model=List[TokenResponse])
async def list_tokens(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.client_id == client_id
        ).order_by(SubscriptionToken.created_at.desc())
    )
    tokens = result.scalars().all()
    
    return [
        TokenResponse(
            id=t.id,
            token=t.token,
            is_active=t.is_active,
            created_at=t.created_at.isoformat() if t.created_at else None,
            expires_at=t.expires_at.isoformat() if t.expires_at else None,
            last_used=t.last_used.isoformat() if t.last_used else None,
        )
        for t in tokens
    ]


@router.post("/{client_id}/tokens/{token_id}/revoke")
async def revoke_token(client_id: int, token_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.id == token_id,
            SubscriptionToken.client_id == client_id
        )
    )
    token = result.scalars().first()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    token.is_active = False
    return {"status": "revoked", "token_id": token_id}


# --- Provisioning Endpoint ---

@router.post("/{client_id}/provision")
async def provision_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get active token
    token_result = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.client_id == client_id,
            SubscriptionToken.is_active == True
        ).order_by(SubscriptionToken.created_at.desc())
    )
    active_token = token_result.scalars().first()
    
    return {
        "status": "provisioning",
        "client_id": client_id,
        "client_name": client.name,
        "portal_url": f"https://{client.subdomain}.mybeacon.co.za",
        "token": active_token.token if active_token else None,
        "steps": [
            "create_tunnel",
            "setup_backup",
            "deploy_addon",
            "verify_access"
        ]
    }


# --- Support Ticket Endpoints ---

class TicketCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "normal"

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    hours_used: Optional[float] = None
    title: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    completed_at: Optional[str] = None
    completed_at: Optional[str] = None
    completed_at: Optional[str] = None
    completed_at: Optional[str] = None
    completed_at: Optional[str] = None

class TicketResponse(BaseModel):
    id: int
    client_id: int
    title: str
    description: Optional[str]
    hours_used: float
    status: str
    priority: str
    created_at: Optional[str]
    updated_at: Optional[str]
    completed_at: Optional[str]


@router.get("/{client_id}/tickets", response_model=List[TicketResponse])
async def list_tickets(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SupportTicket).where(
            SupportTicket.client_id == client_id
        ).order_by(SupportTicket.created_at.desc())
    )
    tickets = result.scalars().all()
    return [
        TicketResponse(
            id=t.id,
            client_id=t.client_id,
            title=t.title,
            description=t.description,
            hours_used=t.hours_used,
            status=t.status,
            priority=t.priority,
            created_at=t.created_at.isoformat() if t.created_at else None,
            updated_at=t.updated_at.isoformat() if t.updated_at else None,
            completed_at=t.completed_at.isoformat() if t.completed_at else None,
        )
        for t in tickets
    ]


@router.post("/{client_id}/tickets", response_model=TicketResponse)
async def create_ticket(client_id: int, ticket: TicketCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    new_ticket = SupportTicket(
        client_id=client_id,
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        status="open",
        hours_used=0.0,
    )
    db.add(new_ticket)
    await db.flush()
    
    return TicketResponse(
        id=new_ticket.id,
        client_id=new_ticket.client_id,
        title=new_ticket.title,
        description=new_ticket.description,
        hours_used=new_ticket.hours_used,
        status=new_ticket.status,
        priority=new_ticket.priority,
        created_at=new_ticket.created_at.isoformat() if new_ticket.created_at else None,
        updated_at=new_ticket.updated_at.isoformat() if new_ticket.updated_at else None,
        completed_at=None,
    )


@router.put("/{client_id}/tickets/{ticket_id}", response_model=TicketResponse)
async def update_ticket(client_id: int, ticket_id: int, update: TicketUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.client_id == client_id
        )
    )
    ticket = result.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    update_data = update.model_dump(exclude_unset=True)
    
    # Parse date strings to datetime objects
    for date_field in ["created_at", "completed_at"]:
        if date_field in update_data and isinstance(update_data[date_field], str):
            update_data[date_field] = datetime.fromisoformat(update_data[date_field])
    
    if update_data.get("status") in ("closed", "completed") and ticket.status not in ("closed", "completed"):
        update_data["completed_at"] = datetime.now()
    
    if "hours_used" in update_data and update_data["hours_used"] != ticket.hours_used:
        diff = update_data["hours_used"] - ticket.hours_used
        client_result = await db.execute(select(Client).where(Client.id == client_id))
        client = client_result.scalars().first()
        if client:
            client.hours_used_this_month = max(0, client.hours_used_this_month + diff)
    
    for key, value in update_data.items():
        setattr(ticket, key, value)
    
    await db.flush()
    
    return TicketResponse(
        id=ticket.id,
        client_id=ticket.client_id,
        title=ticket.title,
        description=ticket.description,
        hours_used=ticket.hours_used,
        status=ticket.status,
        priority=ticket.priority,
        created_at=ticket.created_at.isoformat() if ticket.created_at else None,
        updated_at=ticket.updated_at.isoformat() if ticket.updated_at else None,
        completed_at=ticket.completed_at.isoformat() if ticket.completed_at else None,
    )






@router.delete("/{client_id}/tickets/{ticket_id}")
async def delete_ticket(client_id: int, ticket_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.client_id == client_id
        )
    )
    ticket = result.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    hours_used = ticket.hours_used
    await db.delete(ticket)
    # Adjust client hours if ticket had hours logged
    if hours_used > 0:
        client_result = await db.execute(select(Client).where(Client.id == client_id))
        client = client_result.scalars().first()
        if client:
            client.hours_used_this_month = max(0, client.hours_used_this_month - hours_used)
    return {"status": "deleted", "ticket_id": ticket_id}

@router.get("/{client_id}/tickets/templates")
def ticket_templates(client_id: int):
    templates = [
        {
            "id": "ha-morning-check",
            "category": "Home Assistant",
            "title": "HA Morning Check",
            "description": "Daily Home Assistant health check:\n- Verify HA core is running and responsive\n- Check all integrations are connected\n- Review automation execution logs\n- Confirm all entities are updating correctly\n- Check system resources (CPU, RAM, disk)\n- Verify supervisor add-ons are running\n- Review any error logs in HA",
            "priority": "normal",
            "hours_used": 0.25
        },
        {
            "id": "ha-weekly-check",
            "category": "Home Assistant",
            "title": "HA Weekly Maintenance",
            "description": "Weekly Home Assistant maintenance:\n- Review HA release notes for updates\n- Check all custom components are updated\n- Verify Lovelace dashboards are functional\n- Test critical automations end-to-end\n- Check recorder/database performance\n- Review custom integration configurations\n- Validate backup integrity",
            "priority": "normal",
            "hours_used": 0.5
        },
        {
            "id": "ha-monthly-check",
            "category": "Home Assistant",
            "title": "HA Monthly Audit",
            "description": "Monthly comprehensive HA review:\n- Full system health audit from HA dashboard\n- Review and update HACS components\n- Check for deprecated integrations\n- Optimize automations based on usage patterns\n- Database cleanup and performance check\n- Review user access and permissions\n- Update documentation for any changes\n- Plan next month's improvements",
            "priority": "normal",
            "hours_used": 1.0
        },
        {
            "id": "ha-automation-fix",
            "category": "Home Assistant",
            "title": "HA Automation Fix",
            "description": "HA automation troubleshooting:\n- Identify failing or incomplete automation\n- Review automation trace logs\n- Check entity states and available conditions\n- Test trigger conditions manually\n- Fix automation logic and conditions\n- Verify fix with test run\n- Document changes made",
            "priority": "normal",
            "hours_used": 0.5
        },
        {
            "id": "ha-backup-verify",
            "category": "Home Assistant",
            "title": "HA Backup Verification",
            "description": "HA backup integrity check:\n- Confirm latest HA backup completed successfully\n- Verify backup includes all folders (config, automations, etc)\n- Test partial restore of critical files\n- Check backup file size is reasonable\n- Verify offsite/cloud backup synced\n- Document backup status and any issues",
            "priority": "normal",
            "hours_used": 0.25
        },
        {
            "id": "frigate-morning-check",
            "category": "Frigate",
            "title": "Frigate Morning Check",
            "description": "Daily Frigate NVR health check:\n- Verify all cameras are streaming to Frigate\n- Check detection zones are active and triggering\n- Review overnight recordings for gaps\n- Confirm object detection is working\n- Check snapshot capture is functional\n- Review any false positive patterns\n- Verify retain settings are correct",
            "priority": "normal",
            "hours_used": 0.25
        },
        {
            "id": "frigate-weekly-check",
            "category": "Frigate",
            "title": "Frigate Weekly Maintenance",
            "description": "Weekly Frigate NVR maintenance:\n- Review camera footage quality across all cameras\n- Check motion detection sensitivity settings\n- Optimize detection zones if needed\n- Review and prune old recordings/clips\n- Check GPU hardware acceleration status\n- Verify camera time sync is accurate\n- Review Frigate release notes for updates",
            "priority": "normal",
            "hours_used": 0.5
        },
        {
            "id": "frigate-monthly-check",
            "category": "Frigate",
            "title": "Frigate Monthly Audit",
            "description": "Monthly comprehensive Frigate review:\n- Full camera audit (image quality, positioning, FOV)\n- Review detection accuracy and false positive rate\n- Optimize recording vs detection balance\n- Check storage usage and retention policy\n- Test alert notifications are working\n- Review and update camera-specific settings\n- Benchmark CPU/GPU usage per camera\n- Plan for any camera additions/replacements",
            "priority": "normal",
            "hours_used": 1.0
        },
        {
            "id": "frigate-camera-issue",
            "category": "Frigate",
            "title": "Frigate Camera Issue",
            "description": "Frigate camera troubleshooting:\n- Check camera stream connectivity in Frigate\n- Verify motion detection is triggering\n- Review camera image quality and settings\n- Check night vision / IR performance\n- Test object detection on the camera\n- Review camera-specific Frigate config\n- Check for any ffmpeg errors in logs",
            "priority": "high",
            "hours_used": 0.5
        },
        {
            "id": "frigate-detection-tuning",
            "category": "Frigate",
            "title": "Frigate Detection Tuning",
            "description": "Frigate detection optimization:\n- Review recent false positives and negatives\n- Adjust motion detection thresholds\n- Fine-tune detection zone shapes\n- Test with different lighting conditions\n- Optimize model selection (CPU vs GPU)\n- Update confidence thresholds\n- Document tuning changes",
            "priority": "normal",
            "hours_used": 0.5
        }
    ]

    return templates


@router.get("/{client_id}/report")
async def client_report(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    from datetime import datetime
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    tickets_result = await db.execute(
        select(SupportTicket).where(
            SupportTicket.client_id == client_id,
            SupportTicket.created_at >= month_start
        ).order_by(SupportTicket.created_at.desc())
    )
    month_tickets = tickets_result.scalars().all()
    total_hours = sum(t.hours_used for t in month_tickets)
    open_count = sum(1 for t in month_tickets if t.status == "open")
    closed_count = sum(1 for t in month_tickets if t.status in ("closed", "completed"))
    return {
        "client": {
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "tier": client.tier.value if hasattr(client.tier, "value") else client.tier,
            "monthly_hours_included": client.monthly_hours_included,
            "portal_url": client.portal_url,
        },
        "period": {
            "month": now.strftime("%Y-%m"),
            "start": month_start.isoformat(),
            "end": now.isoformat(),
        },
        "summary": {
            "total_tickets": len(month_tickets),
            "open_tickets": open_count,
            "closed_tickets": closed_count,
            "total_hours_used": total_hours,
            "hours_remaining": max(0, client.monthly_hours_included - total_hours),
        },
        "tickets": [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "hours_used": t.hours_used,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            }
            for t in month_tickets
        ],
    }


@router.get('/{client_id}/hours')
async def get_hours(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail='Client not found')
    from datetime import datetime
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    tickets_result = await db.execute(
        select(SupportTicket).where(
            SupportTicket.client_id == client_id,
            SupportTicket.created_at >= month_start
        )
    )
    month_tickets = tickets_result.scalars().all()
    hours_this_month = sum(t.hours_used for t in month_tickets)
    open_tickets = sum(1 for t in month_tickets if t.status == 'open')
    closed_tickets = sum(1 for t in month_tickets if t.status in ('closed', 'completed'))
    return {
        'client_id': client.id,
        'name': client.name,
        'tier': client.tier.value if hasattr(client.tier, 'value') else client.tier,
        'monthly_hours_included': client.monthly_hours_included,
        'hours_used_this_month': hours_this_month,
        'hours_remaining': max(0, client.monthly_hours_included - hours_this_month),
        'open_tickets': open_tickets,
        'closed_tickets': closed_tickets,
        'total_tickets_this_month': len(month_tickets),
        'month': now.strftime('%Y-%m'),
    }


@router.post('/{client_id}/hours/reset')
async def reset_hours(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail='Client not found')
    client.hours_used_this_month = 0.0
    await db.flush()
    return {'status': 'reset', 'client_id': client_id}
