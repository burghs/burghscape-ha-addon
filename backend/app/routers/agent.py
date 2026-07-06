import os
"""HA Agent endpoints — token-gated."""
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from email_service import send_email
from models import (
    Client, SubscriptionToken, HomeAssistantInstance, 
    ClientStatus, Alert, ClientUser
)

router = APIRouter()

# In-memory cache for agent reports (used by dashboard)
agent_reports = {}


class AgentReport(BaseModel):
    ha_version: str = "unknown"
    entities_count: int = 0
    automations_count: int = 0
    updates_available: List[str] = []
    disk_usage_percent: float = 0
    disk_total_gb: float = 0
    disk_used_gb: float = 0
    cpu_usage_percent: float = 0
    memory_usage_percent: float = 0
    memory_total_gb: float = 0
    memory_used_gb: float = 0
    uptime_seconds: int = 0
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    integrations: Optional[List[str]] = None
    addons: Optional[List[dict]] = None
    addon_version: Optional[str] = None
    cloudflare_tunnel_token: Optional[str] = None
    backup: Optional[dict] = None
    backup_status: Optional[dict] = None
    tailscale: Optional[dict] = None


class AgentStatus(BaseModel):
    status: str
    last_report: Optional[str]
    token_valid: bool
    client_id: Optional[int] = None
    instance_name: Optional[str] = None


async def validate_token(token: str, db: AsyncSession) -> tuple:
    """Validate a subscription token. Returns (client, token_obj) or raises."""
    result = await db.execute(
        select(SubscriptionToken).where(
            SubscriptionToken.token == token,
            SubscriptionToken.is_active == True
        )
    )
    token_obj = result.scalars().first()
    
    if not token_obj:
        raise HTTPException(status_code=401, detail="Invalid or revoked token")
    
    if token_obj.expires_at and token_obj.expires_at < datetime.now():
        token_obj.is_active = False
        raise HTTPException(status_code=401, detail="Token expired")
    
    # Get client
    client_result = await db.execute(
        select(Client).where(Client.id == token_obj.client_id)
    )
    client = client_result.scalars().first()
    
    if not client:
        raise HTTPException(status_code=401, detail="Client not found")
    
    if client.status != ClientStatus.ACTIVE:
        raise HTTPException(status_code=403, detail=f"Client account is {client.status.value}")
    
    # Update last used
    token_obj.last_used = datetime.now()
    
    return client, token_obj


@router.post("/report")
async def agent_report(
    report: AgentReport,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Receive agent report. Requires valid Bearer token in Authorization header."""
    # Extract token from Authorization header
    token = None
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing Authorization header with Bearer token")
    
    # Validate token
    client, token_obj = await validate_token(token, db)
    
    # Find or create instance
    result = await db.execute(
        select(HomeAssistantInstance).where(
            HomeAssistantInstance.client_id == client.id
        ).order_by(HomeAssistantInstance.last_seen.desc())
    )
    instance = result.scalars().first()
    
    now = datetime.now()
    
    if not instance:
        # Create new instance
        instance = HomeAssistantInstance(
            client_id=client.id,
            name=f"{client.name}'s HA",
            ha_version=report.ha_version,
            ip_address=report.ip_address or "0.0.0.0",
            hostname=report.hostname,
            is_online=True,
            disk_usage_percent=report.disk_usage_percent,
            disk_total_gb=report.disk_total_gb,
            disk_used_gb=report.disk_used_gb,
            cpu_usage_percent=report.cpu_usage_percent,
            memory_usage_percent=report.memory_usage_percent,
            memory_total_gb=report.memory_total_gb,
            memory_used_gb=report.memory_used_gb,
            automations_count=report.automations_count,
            entities_count=report.entities_count,
            updates_available=report.updates_available or [],
            integrations=report.integrations or [],
            addons=report.addons or [],
            uptime_seconds=report.uptime_seconds,
            last_seen=now,
        )
        # Store backup data if provided
        if report.backup and report.backup.get("enabled"):
            if report.backup.get("last_backup"):
                try:
                    instance.last_backup = datetime.fromisoformat(report.backup["last_backup"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
            if report.backup.get("next_backup"):
                try:
                    instance.next_backup = datetime.fromisoformat(report.backup["next_backup"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
        db.add(instance)
    else:
        # Check if system was previously offline (coming back online)
        was_offline = not instance.is_online
        previous_version = instance.ha_version
        
        # Update existing instance
        instance.ha_version = report.ha_version
        instance.ip_address = report.ip_address or instance.ip_address
        instance.hostname = report.hostname
        instance.is_online = True
        instance.disk_usage_percent = report.disk_usage_percent
        instance.disk_total_gb = report.disk_total_gb
        instance.disk_used_gb = report.disk_used_gb
        instance.cpu_usage_percent = report.cpu_usage_percent
        instance.memory_usage_percent = report.memory_usage_percent
        instance.memory_total_gb = report.memory_total_gb
        instance.memory_used_gb = report.memory_used_gb
        instance.automations_count = report.automations_count
        instance.entities_count = report.entities_count
        instance.updates_available = report.updates_available or []
        instance.integrations = report.integrations or []
        instance.addons = report.addons or []
        instance.last_seen = now

        # Update backup data if provided
        if report.backup and report.backup.get("enabled"):
            if report.backup.get("last_backup"):
                try:
                    instance.last_backup = datetime.fromisoformat(report.backup["last_backup"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
            if report.backup.get("next_backup"):
                try:
                    instance.next_backup = datetime.fromisoformat(report.backup["next_backup"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
    
    # Send "back online" notification if system recovered
    if was_offline:
        try:
            user_result = await db.execute(
                select(ClientUser).where(ClientUser.client_id == client.id, ClientUser.is_active == True)
            )
            recipients = [u.email for u in user_result.scalars().all()]
            recipients.append("admin@mybeacon.co.za")
            recipients = list(set(r for r in recipients if r))
            
            subject = f"✅ {client.name}'s HA System is Back Online"
            html_body = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
                <h2 style="color:#10b981;">System Back Online ✅</h2>
                <p>Good news! <strong>{client.name}</strong>'s Home Assistant system is back online.</p>
                <div style="background:#f0fdf4;border:1px solid #10b981;border-radius:8px;padding:15px;margin:15px 0;">
                    <p style="margin:5px 0;"><strong>HA Version:</strong> {report.ha_version}</p>
                    <p style="margin:5px 0;"><strong>Entities:</strong> {report.entities_count}</p>
                    <p style="margin:5px 0;"><strong>Restored at:</strong> {now.strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                <p style="color:#666;font-size:13px;">You can access your system at <a href="https://{client.subdomain}.mybeacon.co.za">https://{client.subdomain}.mybeacon.co.za</a></p>
            </div>
            """
            text_body = f"{client.name}'s HA system is back online.\nHA Version: {report.ha_version}\nRestored at: {now.strftime('%Y-%m-%d %H:%M:%S')}\nAccess: https://{client.subdomain}.mybeacon.co.za"
            
            for recipient in recipients:
                send_email(recipient, subject, html_body, text_body)
        except Exception as e:
            print(f"Failed to send online notification: {e}")
    
    # Store cloudflare tunnel token if provided
    if report.cloudflare_tunnel_token:
        client.cloudflare_tunnel_token = report.cloudflare_tunnel_token

    # Store backup status from agent heartbeat
    if report.backup_status:
        bs = report.backup_status
        if bs.get("last_backup"):
            from datetime import datetime as _dt
            try:
                instance.last_backup = _dt.fromtimestamp(bs["last_backup"])
            except (ValueError, TypeError):
                pass
        if bs.get("enabled"):
            interval = bs.get("interval_hours", 24)
            instance.next_backup = instance.last_backup + timedelta(hours=interval) if instance.last_backup else None

    # Store tailscale info
    if report.tailscale:
        ts = report.tailscale
        if ts.get("ip"):
            instance.ip_address = ts["ip"]  # Use Tailscale IP for remote access
    
    await db.flush()
    
    # Update in-memory cache for dashboard
    agent_reports[client.subdomain] = {
        "ha_version": report.ha_version,
        "entities_count": report.entities_count,
        "automations_count": report.automations_count,
        "updates_available": report.updates_available,
        "disk_usage_percent": report.disk_usage_percent,
        "disk_total_gb": report.disk_total_gb,
        "disk_used_gb": report.disk_used_gb,
        "cpu_usage_percent": report.cpu_usage_percent,
        "memory_usage_percent": report.memory_usage_percent,
        "memory_total_gb": report.memory_total_gb,
        "memory_used_gb": report.memory_used_gb,
        "uptime_seconds": report.uptime_seconds,
        "addons": report.addons,
        "integrations": report.integrations,
        "ip_address": report.ip_address,
        "is_online": True,
        "last_seen": now.isoformat(),
        "backup": report.backup,
        "backup_status": report.backup_status,
        "tailscale": report.tailscale,
        "client_id": client.id,
        "client_name": client.name,
    }
    
    return {
        "status": "accepted",
        "client_id": client.id,
        "instance_id": instance.id,
        "timestamp": now.isoformat(),
    }



@router.get("/config")
async def get_agent_config(authorization: str = Header(None)):
    """Return add-on configuration for an agent, including Tailscale key and backup settings.
    
    The agent calls this on first run to get all config values that shouldn't be
    entered manually (Tailscale auth key, backup SFTP host, etc.)
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    
    token = authorization.replace("Bearer ", "")
    
    from database import async_session as AsyncSessionLocal
    from sqlalchemy import select
    from models import SubscriptionToken, Client, HomeAssistantInstance
    
    async with AsyncSessionLocal() as db:
        # Validate token
        result = await db.execute(
            select(SubscriptionToken).where(
                SubscriptionToken.token == token,
                SubscriptionToken.is_active == True
            )
        )
        token_obj = result.scalars().first()
        if not token_obj:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        client_result = await db.execute(
            select(Client).where(Client.id == token_obj.client_id)
        )
        client = client_result.scalars().first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        # Get or generate Tailscale auth key
        tailscale_key = client.tailscale_authkey
        if not tailscale_key:
            try:
                from services.tailscale import generate_auth_key
                from config import get_settings
                import asyncio
                settings = get_settings()
                tailscale_key = await generate_auth_key(settings)
                if tailscale_key:
                    client.tailscale_authkey = tailscale_key
                    await db.flush()
            except Exception:
                pass
        
        # Get backup settings from platform env
        import os
        from config import get_settings
        settings = get_settings()
        
        # Find the instance for this client (most recent)
        inst_result = await db.execute(
            select(HomeAssistantInstance).where(
                HomeAssistantInstance.client_id == client.id
            ).order_by(HomeAssistantInstance.created_at.desc())
        )
        instance = inst_result.scalars().first()
        
        return {
            "client_id": client.id,
            "client_name": client.name,
            "subdomain": client.subdomain,
            "instance_id": instance.id if instance else None,
            "instance_name": instance.name if instance else client.name,
            "tailscale_authkey": tailscale_key or "",
            "backup_enabled": bool(settings.BACKUP_SFTP_HOST),
            "backup_sftp_host": settings.BACKUP_SFTP_HOST,
            "backup_sftp_user": settings.BACKUP_SFTP_USER,
            "backup_sftp_path": settings.BACKUP_SFTP_PATH,
            "backup_interval_hours": 24,
            "backup_keep_count": 3,
            "backup_ssh_key": open("/app/config/backup_key").read() if os.path.isfile("/app/config/backup_key") else "",
            "cloudflare_tunnel_id": client.cloudflare_tunnel_id or "",
            "cloudflare_tunnel_token": client.cloudflare_tunnel_token or "",
        }


@router.get("/status")
async def agent_status(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Check agent status and validate token."""
    token = None
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value
    
    if not token:
        return AgentStatus(
            status="unauthorized",
            last_report=None,
            token_valid=False,
        )
    
    try:
        client, token_obj = await validate_token(token, db)
    except HTTPException as e:
        return AgentStatus(
            status="unauthorized",
            last_report=None,
            token_valid=False,
        )
    
    # Get last report time
    result = await db.execute(
        select(HomeAssistantInstance).where(
            HomeAssistantInstance.client_id == client.id
        ).order_by(HomeAssistantInstance.last_seen.desc())
    )
    instance = result.scalars().first()
    
    return AgentStatus(
        status="online",
        last_report=instance.last_seen.isoformat() if instance and instance.last_seen else None,
        token_valid=True,
        client_id=client.id,
        instance_name=instance.name if instance else None,
    )


@router.get("/validate")
async def validate_token_endpoint(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Validate a token and return client info (used by add-on for initial check)."""
    token = None
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    
    client, token_obj = await validate_token(token, db)
    
    return {
        "valid": True,
        "client": {
            "id": client.id,
            "name": client.name,
            "subdomain": client.subdomain,
            "tier": client.tier.value if hasattr(client.tier, 'value') else client.tier,
            "status": client.status.value if hasattr(client.status, 'value') else client.status,
            "portal_url": f"https://{client.subdomain}.mybeacon.co.za",
        },
        "expires_at": token_obj.expires_at.isoformat() if token_obj.expires_at else None,
    }
