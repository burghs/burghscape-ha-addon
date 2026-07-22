"""Burghscape Home Cloud Platform - Main Application."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from sqlalchemy import select, func, update

from config import get_settings
from database import init_db, engine, async_session
from routers import clients, instances, backups, backup_state, support, monitoring, auth, agent, tunnels, portal, portal_users, branding, campaigns, campaign_popups, onboarding, campaign_notifications
from middleware import AdminAuthMiddleware
from admin_auth import admin_auth_router
from models import Client, HomeAssistantInstance, Alert, SupportTicket, Backup, SubscriptionToken

settings = get_settings()

STALE_CHECK_INTERVAL = 60  # Check every 60 seconds
STALE_THRESHOLD_MINUTES = 5  # Mark offline after 5 minutes without heartbeat


# Track which instances we've already sent offline alerts for
_offline_alerted = set()


def clear_offline_alert(instance_id: int):
    """Clear offline alert tracking when instance comes back online."""
    _offline_alerted.discard(instance_id)


async def check_stale_instances():
    """Periodically mark instances as offline if no heartbeat received. Send email on offline detection."""
    logger.info("Stale instance checker task running")
    while True:
        try:
            await asyncio.sleep(STALE_CHECK_INTERVAL)
            async with async_session() as session:
                cutoff = datetime.now() - timedelta(minutes=STALE_THRESHOLD_MINUTES)
                
                # Find instances that will be marked offline (for email notification)
                stale_result = await session.execute(
                    select(HomeAssistantInstance, Client)
                    .join(Client, HomeAssistantInstance.client_id == Client.id)
                    .where(
                        HomeAssistantInstance.is_online == True,
                        HomeAssistantInstance.last_seen < cutoff
                    )
                )
                stale_instances = stale_result.all()
                
                # Mark them offline
                result = await session.execute(
                    update(HomeAssistantInstance)
                    .where(
                        HomeAssistantInstance.is_online == True,
                        HomeAssistantInstance.last_seen < cutoff
                    )
                    .values(is_online=False)
                )
                await session.commit()
                
                if result.rowcount > 0:
                    logger.info(f"Marked {result.rowcount} instance(s) as offline (stale heartbeat)")
                    
                    # Send offline notification emails
                    from email_service import send_email
                    from models import ClientUser
                    
                    for instance, client in stale_instances:
                        instance_id = instance.id
                        if instance_id in _offline_alerted:
                            continue
                        if not instance.send_alerts:
                            _offline_alerted.add(instance_id)
                            continue
                        _offline_alerted.add(instance_id)
                        
                        try:
                            # Get client portal users
                            user_result = await session.execute(
                                select(ClientUser).where(
                                    ClientUser.client_id == client.id,
                                    ClientUser.is_active == True
                                )
                            )
                            recipients = [u.email for u in user_result.scalars().all()]
                            recipients.append("admin@mybeacon.co.za")
                            recipients = list(set(r for r in recipients if r))
                            
                            last_seen_str = instance.last_seen.strftime('%Y-%m-%d %H:%M:%S') if instance.last_seen else 'Unknown'
                            subject = f"⚠️ {client.name}'s HA System Appears Offline"
                            html_body = f"""
                            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
                                <h2 style="color:#ef4444;">System Offline Alert ⚠️</h2>
                                <p>We've lost contact with <strong>{client.name}</strong>'s Home Assistant system.</p>
                                <div style="background:#fef2f2;border:1px solid #ef4444;border-radius:8px;padding:15px;margin:15px 0;">
                                    <p style="margin:5px 0;"><strong>HA Version:</strong> {instance.ha_version or 'Unknown'}</p>
                                    <p style="margin:5px 0;"><strong>Last Seen:</strong> {last_seen_str}</p>
                                    <p style="margin:5px 0;"><strong>Detected at:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                                </div>
                                <p style="color:#666;font-size:13px;">This may be due to internet connectivity issues, power outage, or system maintenance. We'll notify you when it's back online.</p>
                            </div>
                            """
                            text_body = f"OFFLINE ALERT: {client.name}'s HA system is unreachable.\nLast seen: {last_seen_str}\nWe will notify you when it recovers."
                            
                            for recipient in recipients:
                                send_email(recipient, subject, html_body, text_body)
                        except Exception as e:
                            logger.error(f"Failed to send offline alert for {client.name}: {e}")
                else:
                    logger.debug("Stale check: no instances to mark offline")
                    
                # Check for recovered instances - send online-back notification
                online_insts = await session.execute(
                    select(HomeAssistantInstance, Client)
                    .join(Client, HomeAssistantInstance.client_id == Client.id)
                    .where(
                        HomeAssistantInstance.is_online == True,
                        HomeAssistantInstance.last_seen >= cutoff,
                        HomeAssistantInstance.send_alerts == True,
                    )
                )
                recovered_ids = set()
                for inst, cli in online_insts.all():
                    rid = inst.id
                    if rid in _offline_alerted:
                        logger.info(f"Instance {inst.name} came back online")
                        recovered_ids.add(rid)
                        try:
                            from email_service import send_email
                            from models import ClientUser
                            u_result = await session.execute(
                                select(ClientUser).where(
                                    ClientUser.client_id == cli.id,
                                    ClientUser.is_active == True,
                                )
                            )
                            recipients = [u.email for u in u_result.scalars().all()]
                            recipients.append("admin@mybeacon.co.za")
                            recipients = list(set(r for r in recipients if r))
                            ls = inst.last_seen.strftime("%Y-%m-%d %H:%M:%S") if inst.last_seen else "Unknown"
                            subject = cli.name + " HA System is Back Online"
                            html = "<div style='font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;'>"
                            html += "<h2 style='color:#22c55e;'>System Recovered</h2>"
                            html += "<p><strong>" + cli.name + "</strong> Home Assistant is back online!</p>"
                            html += "<div style='background:#f0fdf4;border:1px solid #22c55e;border-radius:8px;padding:15px;margin:15px 0;'>"
                            html += "<p>HA Version: " + (inst.ha_version or "Unknown") + "</p>"
                            html += "<p>Last Seen: " + ls + "</p></div></div>"
                            txt = "RECOVERY: " + cli.name + " HA system is back online. Last seen: " + ls
                            for r in recipients:
                                send_email(r, subject, html, txt)
                        except Exception as e:
                            logger.error(f"Recovery email failed: {e}")

                # Clean up _offline_alerted
                _offline_alerted.difference_update(recovered_ids)
                
        except asyncio.CancelledError:
            logger.info("Stale instance checker cancelled")
            break
        except Exception as e:
            logger.error(f"Error in stale instance checker: {e}", exc_info=True)
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await init_db()
    logger.info("Database initialized")
    
    # Start background task for stale instance detection
    stale_task = asyncio.create_task(check_stale_instances())
    logger.info("Stale instance checker started")
    
    yield
    
    logger.info("Shutting down...")
    stale_task.cancel()
    try:
        await stale_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Managed Home Assistant Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AdminAuthMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
@app.get("/api/health")
async def health_check():
    database_status = "unavailable"
    try:
        async with async_session() as db:
            await db.execute(select(1))
        database_status = "connected"
    except Exception:
        pass
    storage_available = bool(settings.BACKUP_LOCAL_PATH and os.path.isdir(settings.BACKUP_LOCAL_PATH) and os.access(settings.BACKUP_LOCAL_PATH, os.R_OK | os.W_OK))
    email_configured = bool(os.environ.get("SMTP_HOST"))
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "commit": os.environ.get("BUILD_COMMIT", "unknown"),
        "database": database_status,
        "storage": "available" if storage_available else "unavailable",
        "email": "configured" if email_configured else "not_configured",
    }


app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(admin_auth_router, prefix="/api/admin", tags=["Admin Auth"])
app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
app.include_router(instances.router, prefix="/api/instances", tags=["HA Instances"])
app.include_router(backups.router, prefix="/api/backups", tags=["Backups"])
app.include_router(backup_state.router, tags=["Managed Backup State"])
app.include_router(support.router, prefix="/api/support", tags=["Support"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoring"])
app.include_router(tunnels.router, prefix="/api/tunnels", tags=["Tunnels"])
app.include_router(portal_users.router, prefix="/api/portal", tags=["Portal"])
app.include_router(portal.router, tags=["Portal"])
app.include_router(branding.router, prefix="/api", tags=["Branding"])
app.include_router(campaigns.router, tags=["Campaigns"])
app.include_router(campaign_popups.router, tags=["Campaign Popups"])
app.include_router(campaign_notifications.router, tags=["Campaign Notifications"])
app.include_router(onboarding.router, tags=["Client Onboarding"])


# Static files for brand assets
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/api/dashboard/summary")
async def dashboard_summary():
    """Real-time dashboard summary from database."""
    async with async_session() as session:
        client_result = await session.execute(select(func.count(Client.id)))
        total_clients = client_result.scalar() or 0
        
        active_result = await session.execute(
            select(func.count(Client.id)).where(Client.status == "active")
        )
        active_clients = active_result.scalar() or 0
        
        online_result = await session.execute(
            select(func.count(HomeAssistantInstance.id)).where(
                HomeAssistantInstance.is_online == True
            )
        )
        online_instances = online_result.scalar() or 0
        
        total_inst_result = await session.execute(select(func.count(HomeAssistantInstance.id)))
        total_instances = total_inst_result.scalar() or 0
        
        alerts_result = await session.execute(
            select(func.count(Alert.id)).where(Alert.is_resolved == False)
        )
        alerts_unresolved = alerts_result.scalar() or 0
        
        support_result = await session.execute(
            select(func.count(SupportTicket.id)).where(SupportTicket.status == "open")
        )
        support_open = support_result.scalar() or 0
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        backups_result = await session.execute(
            select(func.count(Backup.id)).where(
                Backup.started_at >= today_start,
                Backup.status == "completed"
            )
        )
        backups_today = backups_result.scalar() or 0
        
        failed_result = await session.execute(
            select(func.count(Backup.id)).where(
                Backup.started_at >= today_start,
                Backup.status == "failed"
            )
        )
        backups_failed = failed_result.scalar() or 0
        
        offline_instances = total_instances - online_instances
        
        return {
            "total_clients": total_clients,
            "active_clients": active_clients,
            "online_instances": online_instances,
            "offline_instances": offline_instances,
            "backups_today": backups_today,
            "backups_failed": backups_failed,
            "alerts_unresolved": alerts_unresolved,
            "support_open": support_open,
        }
