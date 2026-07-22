"""RC1.4.1 campaign administration, targeting, media, and client read-state APIs."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional
from urllib.parse import urlparse
import logging
import os
import secrets

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_auth import get_current_admin
from config import get_settings
from database import get_db
from models import Campaign, CampaignReadState, CampaignTarget, Client, ClientStatus, ClientUser
from routers.portal_state import portal_sessions

router = APIRouter()
logger = logging.getLogger("burghscape.campaigns")
TYPES = {
    "announcement": "Announcement", "promotion": "Promotion", "new_service": "New Service",
    "maintenance_notice": "Maintenance Notice", "tip": "Tip",
    "featured_project": "Featured Project", "important_notice": "Important Notice",
}
STATUSES = {"draft", "published", "archived"}
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
IMAGE_SIGNATURES = {
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}


class CampaignInput(BaseModel):
    internal_name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    subtitle: Optional[str] = Field(default=None, max_length=500)
    campaign_type: str
    body_content: str = Field(min_length=1, max_length=20000)
    price_text: Optional[str] = Field(default=None, max_length=100)
    regular_price_text: Optional[str] = Field(default=None, max_length=100)
    call_to_action_label: Optional[str] = Field(default=None, max_length=100)
    call_to_action_url: Optional[str] = Field(default=None, max_length=1000)
    popup_enabled: bool = False
    popup_summary: Optional[str] = Field(default=None, max_length=500)
    priority: int = Field(default=0, ge=-1000, le=1000)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    target_all_clients: bool = True
    target_client_ids: list[int] = Field(default_factory=list)


def now_utc():
    return datetime.utcnow()


def database_datetime(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize API timestamps to naive UTC for the existing PostgreSQL columns."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def api_datetime(value: Optional[datetime]) -> Optional[str]:
    return f"{value.isoformat()}Z" if value else None


def valid_action_url(value: Optional[str]) -> bool:
    if not value:
        return True
    if any(character in value for character in ("\r", "\n", "\\")):
        return False
    parsed = urlparse(value)
    if not parsed.scheme and not parsed.netloc:
        return parsed.path in {"/portal", "/portal/whats-new", "/portal/getting-started"}
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


def validate_input(data: CampaignInput, publishing: bool = False, server_now: Optional[datetime] = None):
    if data.campaign_type not in TYPES:
        raise HTTPException(422, "Invalid campaign type")
    if data.starts_at and data.ends_at and data.ends_at <= data.starts_at:
        raise HTTPException(422, "End date must be after start date")
    if not data.target_all_clients and not data.target_client_ids:
        raise HTTPException(422, "Selected-client targeting requires at least one client")
    if data.call_to_action_url and not valid_action_url(data.call_to_action_url):
        raise HTTPException(422, "Action URL must be an approved portal route or valid HTTPS URL")
    if publishing and not data.title.strip():
        raise HTTPException(422, "Campaign title is required")
    if publishing and data.ends_at and data.ends_at <= (server_now or now_utc()):
        raise HTTPException(422, "Campaign end date must be in the future")


async def target_ids(db: AsyncSession, campaign_id: int) -> list[int]:
    return list((await db.execute(select(CampaignTarget.client_id).where(CampaignTarget.campaign_id == campaign_id))).scalars().all())


def delivery_status(campaign: Campaign) -> str:
    now = now_utc()
    if campaign.status == "archived": return "archived"
    if campaign.status != "published": return "draft"
    if campaign.starts_at and campaign.starts_at > now: return "scheduled"
    if campaign.ends_at and campaign.ends_at <= now: return "expired"
    return "live"

def admin_payload(campaign: Campaign, targets: list[int]) -> dict:
    return {
        "id": campaign.id, "internal_name": campaign.internal_name, "title": campaign.title,
        "subtitle": campaign.subtitle, "campaign_type": campaign.campaign_type,
        "campaign_type_label": TYPES.get(campaign.campaign_type, campaign.campaign_type),
        "body_content": campaign.body_content, "price_text": campaign.price_text,
        "regular_price_text": campaign.regular_price_text,
        "call_to_action_label": campaign.call_to_action_label,
        "call_to_action_url": campaign.call_to_action_url,
        "popup_enabled": campaign.popup_enabled, "popup_summary": campaign.popup_summary,
        "has_image": bool(campaign.image_reference),
        "image_url": f"/api/admin/campaigns/{campaign.id}/image-file" if campaign.image_reference else None,
        "status": campaign.status, "delivery_status": delivery_status(campaign), "priority": campaign.priority,
        "starts_at": api_datetime(campaign.starts_at),
        "ends_at": api_datetime(campaign.ends_at),
        "published_at": campaign.published_at.isoformat() if campaign.published_at else None,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
        "created_by": campaign.created_by, "updated_by": campaign.updated_by,
        "target_all_clients": campaign.target_all_clients, "target_client_ids": targets,
        "archived_at": campaign.archived_at.isoformat() if campaign.archived_at else None,
    }


def client_payload(campaign: Campaign, is_read: bool) -> dict:
    return {
        "id": campaign.id, "title": campaign.title, "subtitle": campaign.subtitle,
        "campaign_type": campaign.campaign_type,
        "campaign_type_label": TYPES.get(campaign.campaign_type, campaign.campaign_type),
        "body_content": campaign.body_content, "price_text": campaign.price_text,
        "regular_price_text": campaign.regular_price_text,
        "has_image": bool(campaign.image_reference),
        "image_url": f"/api/portal/campaigns/{campaign.id}/image" if campaign.image_reference else None,
        "published_at": campaign.published_at.isoformat() if campaign.published_at else None,
        "starts_at": api_datetime(campaign.starts_at),
        "ends_at": api_datetime(campaign.ends_at),
        "is_read": is_read,
    }


async def portal_user(request: Request, db: AsyncSession) -> ClientUser:
    user_id = portal_sessions.get(request.cookies.get("portal_token", ""))
    if not user_id:
        raise HTTPException(401, "Portal authentication required")
    user = (await db.execute(select(ClientUser).where(ClientUser.id == user_id, ClientUser.is_active == True))).scalars().first()
    if not user:
        raise HTTPException(401, "Portal authentication required")
    client = (await db.execute(select(Client).where(Client.id == user.client_id, Client.status == ClientStatus.ACTIVE))).scalars().first()
    if not client:
        raise HTTPException(403, "Client account is unavailable")
    return user


def visible_clause(client_id: int, now: datetime):
    targeted = exists(select(CampaignTarget.campaign_id).where(
        CampaignTarget.campaign_id == Campaign.id, CampaignTarget.client_id == client_id
    ))
    return and_(
        Campaign.status == "published", Campaign.published_at.is_not(None),
        or_(Campaign.starts_at.is_(None), Campaign.starts_at <= now),
        or_(Campaign.ends_at.is_(None), Campaign.ends_at > now),
        or_(Campaign.target_all_clients == True, targeted),
    )


async def campaign_or_404(db, campaign_id):
    campaign = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalars().first()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return campaign


async def apply_targets(db, campaign, ids):
    if campaign.target_all_clients:
        await db.execute(delete(CampaignTarget).where(CampaignTarget.campaign_id == campaign.id))
        return
    existing = set((await db.execute(select(Client.id).where(Client.id.in_(ids)))).scalars().all())
    if existing != set(ids):
        raise HTTPException(422, "One or more target clients are invalid")
    await db.execute(delete(CampaignTarget).where(CampaignTarget.campaign_id == campaign.id))
    for client_id in sorted(existing):
        db.add(CampaignTarget(campaign_id=campaign.id, client_id=client_id))


@router.get("/api/admin/campaign-types")
async def list_campaign_types(admin: dict = Depends(get_current_admin)):
    return [{"value": value, "label": label} for value, label in TYPES.items()]


@router.get("/api/admin/campaign-target-clients")
async def list_target_clients(admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    clients = (await db.execute(select(Client).order_by(Client.name))).scalars().all()
    return [{"id": c.id, "name": c.name, "status": c.status.value if hasattr(c.status, "value") else c.status} for c in clients]


@router.get("/api/admin/campaigns")
async def list_campaigns(admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    campaigns = (await db.execute(select(Campaign).order_by(Campaign.priority.desc(), Campaign.created_at.desc()))).scalars().all()
    return {"campaigns": [admin_payload(c, await target_ids(db, c.id)) for c in campaigns]}


@router.get("/api/admin/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    campaign = await campaign_or_404(db, campaign_id)
    return admin_payload(campaign, await target_ids(db, campaign.id))


@router.post("/api/admin/campaigns", status_code=201)
async def create_campaign(data: CampaignInput, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    validate_input(data)
    if (await db.execute(select(Campaign.id).where(Campaign.internal_name == data.internal_name.strip()))).scalar():
        raise HTTPException(409, "Internal name already exists")
    values = data.model_dump(exclude={"target_client_ids"})
    values["starts_at"] = database_datetime(data.starts_at)
    values["ends_at"] = database_datetime(data.ends_at)
    campaign = Campaign(**values, status="draft",
                        created_by=admin["username"], updated_by=admin["username"])
    db.add(campaign)
    await db.flush()
    await apply_targets(db, campaign, data.target_client_ids)
    await db.commit()
    await db.refresh(campaign)
    return admin_payload(campaign, await target_ids(db, campaign.id))


@router.put("/api/admin/campaigns/{campaign_id}")
async def update_campaign(campaign_id: int, data: CampaignInput, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    validate_input(data)
    campaign = await campaign_or_404(db, campaign_id)
    if campaign.status == "archived":
        raise HTTPException(409, "Archived campaigns cannot be edited")
    duplicate = (await db.execute(select(Campaign.id).where(Campaign.internal_name == data.internal_name.strip(), Campaign.id != campaign.id))).scalar()
    if duplicate:
        raise HTTPException(409, "Internal name already exists")
    values = data.model_dump(exclude={"target_client_ids"})
    values["starts_at"] = database_datetime(data.starts_at)
    values["ends_at"] = database_datetime(data.ends_at)
    for key, value in values.items():
        setattr(campaign, key, value)
    campaign.updated_by = admin["username"]
    campaign.updated_at = now_utc()
    await apply_targets(db, campaign, data.target_client_ids)
    await db.commit()
    return admin_payload(campaign, await target_ids(db, campaign.id))


async def lifecycle(campaign_id, action, admin, db):
    campaign = await campaign_or_404(db, campaign_id)
    if action == "publish":
        publish_time = now_utc()
        data = CampaignInput(**{k: getattr(campaign, k) for k in CampaignInput.model_fields if k != "target_client_ids"},
                             target_client_ids=await target_ids(db, campaign.id))
        validate_input(data, True, publish_time)
        campaign.status = "published"
        campaign.published_at = publish_time
        campaign.archived_at = None
    elif action == "unpublish":
        if campaign.status != "published":
            raise HTTPException(409, "Only published campaigns can be unpublished")
        campaign.status = "draft"
        campaign.published_at = None
    elif action == "archive":
        campaign.status = "archived"
        campaign.archived_at = now_utc()
    campaign.updated_by = admin["username"]
    campaign.updated_at = now_utc()
    await db.commit()
    return admin_payload(campaign, await target_ids(db, campaign.id))


@router.post("/api/admin/campaigns/{campaign_id}/publish")
async def publish(campaign_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await lifecycle(campaign_id, "publish", admin, db)


@router.post("/api/admin/campaigns/{campaign_id}/unpublish")
async def unpublish(campaign_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await lifecycle(campaign_id, "unpublish", admin, db)


@router.post("/api/admin/campaigns/{campaign_id}/archive")
async def archive(campaign_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await lifecycle(campaign_id, "archive", admin, db)


def media_root() -> Path:
    root = Path(get_settings().CAMPAIGN_MEDIA_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_media_path(reference: str) -> Path:
    if not reference or Path(reference).name != reference:
        raise ValueError("Invalid campaign media reference")
    root = media_root()
    path = (root / reference).resolve()
    path.relative_to(root)
    return path


async def save_image(upload: UploadFile) -> tuple[Path, str]:
    content_type = (upload.content_type or "").lower()
    original_ext = Path(upload.filename or "").suffix.lower()
    expected_ext = IMAGE_TYPES.get(content_type)
    if not expected_ext or original_ext not in ({".jpg", ".jpeg"} if expected_ext == ".jpg" else {expected_ext}):
        raise HTTPException(415, "Only JPEG, PNG, and WebP images are supported")
    max_bytes = get_settings().CAMPAIGN_MAX_IMAGE_BYTES
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, "Campaign image exceeds the configured size limit")
    if not data or not IMAGE_SIGNATURES[content_type](data):
        raise HTTPException(415, "Image content does not match its declared type")
    name = f"{secrets.token_hex(20)}{expected_ext}"
    final = safe_media_path(name)
    temp = final.with_suffix(final.suffix + ".tmp")
    try:
        async with aiofiles.open(temp, "wb") as handle:
            await handle.write(data)
        os.replace(temp, final)
    finally:
        if temp.exists():
            temp.unlink()
    return final, content_type


@router.post("/api/admin/campaigns/{campaign_id}/image")
async def upload_image(campaign_id: int, image: UploadFile = File(...), admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    campaign = await campaign_or_404(db, campaign_id)
    old = campaign.image_reference
    final, content_type = await save_image(image)
    try:
        campaign.image_reference = final.name
        campaign.image_content_type = content_type
        campaign.updated_by = admin["username"]
        await db.commit()
    except Exception:
        await db.rollback()
        final.unlink(missing_ok=True)
        raise HTTPException(500, "Campaign image could not be saved")
    if old:
        try: safe_media_path(old).unlink(missing_ok=True)
        except OSError: logger.warning("Superseded campaign image cleanup failed campaign_id=%s", campaign.id)
    return admin_payload(campaign, await target_ids(db, campaign.id))


@router.delete("/api/admin/campaigns/{campaign_id}/image")
async def remove_image(campaign_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    campaign = await campaign_or_404(db, campaign_id)
    old = campaign.image_reference
    campaign.image_reference = None
    campaign.image_content_type = None
    campaign.updated_by = admin["username"]
    await db.commit()
    if old:
        try: safe_media_path(old).unlink(missing_ok=True)
        except OSError: logger.warning("Campaign image removal cleanup failed campaign_id=%s", campaign.id)
    return {"status": "removed"}


@router.delete("/api/admin/campaigns/{campaign_id}")
async def delete_draft(campaign_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    campaign = await campaign_or_404(db, campaign_id)
    if campaign.status != "draft":
        raise HTTPException(409, "Only draft campaigns can be deleted")
    old = campaign.image_reference
    await db.delete(campaign)
    await db.commit()
    if old:
        try: safe_media_path(old).unlink(missing_ok=True)
        except OSError: logger.warning("Deleted draft media cleanup failed campaign_id=%s", campaign_id)
    return {"status": "deleted"}


async def media_response(campaign, client_visible=False):
    if not campaign.image_reference:
        raise HTTPException(404, "Campaign image not found")
    try:
        path = safe_media_path(campaign.image_reference)
    except ValueError:
        raise HTTPException(404, "Campaign image not found")
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, "Campaign image not found")
    return FileResponse(path, media_type=campaign.image_content_type or "application/octet-stream")


@router.get("/api/admin/campaigns/{campaign_id}/image-file")
async def admin_image(campaign_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await media_response(await campaign_or_404(db, campaign_id))


async def visible_campaign(db, campaign_id, user):
    return (await db.execute(select(Campaign).where(Campaign.id == campaign_id, visible_clause(user.client_id, now_utc())))).scalars().first()


@router.get("/api/portal/campaigns")
async def portal_campaigns(request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db)
    campaigns = (await db.execute(select(Campaign).where(visible_clause(user.client_id, now_utc())).order_by(Campaign.priority.desc(), Campaign.published_at.desc()))).scalars().all()
    read_ids = set((await db.execute(select(CampaignReadState.campaign_id).where(CampaignReadState.client_user_id == user.id))).scalars().all())
    return {"campaigns": [client_payload(c, c.id in read_ids) for c in campaigns],
            "unread_count": sum(1 for c in campaigns if c.id not in read_ids)}


@router.get("/api/portal/campaigns/unread-count")
async def unread_count(request: Request, db: AsyncSession = Depends(get_db)):
    data = await portal_campaigns(request, db)
    return {"unread_count": data["unread_count"]}


@router.get("/api/portal/campaigns/{campaign_id}")
async def portal_campaign(campaign_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db)
    campaign = await visible_campaign(db, campaign_id, user)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    read = (await db.execute(select(CampaignReadState.id).where(CampaignReadState.campaign_id == campaign.id, CampaignReadState.client_user_id == user.id))).scalar()
    return client_payload(campaign, bool(read))


@router.post("/api/portal/campaigns/{campaign_id}/read")
async def mark_read(campaign_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db)
    campaign = await visible_campaign(db, campaign_id, user)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    existing = (await db.execute(select(CampaignReadState).where(CampaignReadState.campaign_id == campaign.id, CampaignReadState.client_user_id == user.id))).scalars().first()
    if not existing:
        db.add(CampaignReadState(campaign_id=campaign.id, client_user_id=user.id, read_at=now_utc()))
        await db.commit()
    return {"status": "read"}


@router.get("/api/portal/campaigns/{campaign_id}/image")
async def portal_image(campaign_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db)
    campaign = await visible_campaign(db, campaign_id, user)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return await media_response(campaign)

WHATS_NEW_HTML = """<!doctype html><html lang="en" data-theme-enabled><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="/static/theme.js"></script><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="/static/theme.css"><title>What’s New - Burghscape</title><style>.campaign-body{white-space:pre-line}.modal-layer{position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;padding:1rem;background:rgba(3,7,18,.8)}.modal-layer[hidden]{display:none}.modal-panel{max-height:calc(100dvh - 2rem);overflow:auto}.campaign-image{aspect-ratio:16/7;object-fit:cover}@media(max-width:640px){.details-button{width:100%;min-height:44px}}</style></head><body class="min-h-screen bg-gray-950 text-gray-200 bg-grid"><nav class="card border-b border-white/10 px-4 py-3"><div class="mx-auto flex max-w-6xl items-center justify-between gap-3"><a href="/portal" class="flex items-center gap-3"><img src="/static/brand/burghscape-shield.svg" alt="Burghscape" class="h-10 w-10"><span class="font-semibold text-white">Burghscape Client Portal</span></a><div class="flex gap-2"><a href="/portal" class="touch-action text-gray-300">Dashboard</a><a href="/portal/logout" class="touch-action text-gray-300">Logout</a></div></div></nav><main class="mx-auto max-w-6xl px-4 py-6 sm:px-6"><p class="text-sm font-semibold uppercase tracking-[.16em] text-purple-300">Client updates</p><h1 class="mt-2 text-3xl font-bold text-white">What’s New</h1><p class="mt-2 text-gray-400">Announcements, service updates, maintenance notices, and useful tips from Burghscape.</p><div id="campaign-list" class="mt-6 grid gap-4 md:grid-cols-2"><p class="text-gray-400">Loading updates…</p></div></main><div id="campaign-modal" class="modal-layer" hidden role="dialog" aria-modal="true" aria-labelledby="campaign-title"><div class="modal-panel card w-full max-w-2xl p-5 sm:p-7" tabindex="-1"><div class="flex justify-end"><button id="campaign-close" type="button" class="touch-action" aria-label="Close campaign details">Close</button></div><div id="campaign-detail"></div></div></div><script src="/static/campaigns-client.js"></script></body></html>"""

@router.get("/portal/whats-new", response_class=HTMLResponse)
async def whats_new_page(request: Request, db: AsyncSession = Depends(get_db)):
    await portal_user(request, db)
    return HTMLResponse(WHATS_NEW_HTML)
