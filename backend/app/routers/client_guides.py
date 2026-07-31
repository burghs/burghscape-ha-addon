"""Protected reusable Client Guides publishing and client delivery."""
from datetime import datetime
from html import escape
from pathlib import Path
import os
import secrets
from typing import Literal

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_auth import get_current_admin
from config import get_settings
from database import get_db
from models import Client, ClientGuide, ClientGuideAssignment, ClientUser, SecurityAuditEvent
from routers.portal_state import portal_sessions

router = APIRouter()
MIME_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "application/pdf": ".pdf"}

def _valid_content(mime: str, data: bytes) -> bool:
    return bool(data) and {
        "image/png": lambda: data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": lambda: data.startswith(b"\xff\xd8\xff"),
        "image/webp": lambda: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
        "application/pdf": lambda: data.startswith(b"%PDF-"),
    }.get(mime, lambda: False)()

def guide_root() -> Path:
    root = Path(get_settings().GUIDE_MEDIA_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root

def safe_guide_path(name: str) -> Path:
    if not name or Path(name).name != name:
        raise ValueError("invalid guide storage name")
    path = (guide_root() / name).resolve()
    path.relative_to(guide_root())
    return path

async def save_upload(upload: UploadFile) -> tuple[Path, str, int, str]:
    mime = (upload.content_type or "").lower()
    extension = MIME_EXTENSIONS.get(mime)
    if not extension:
        raise HTTPException(415, "PNG, JPEG, WebP, or PDF files are required")
    maximum = get_settings().GUIDE_MAX_UPLOAD_BYTES
    data = await upload.read(maximum + 1)
    if len(data) > maximum:
        raise HTTPException(413, "Guide file exceeds the configured size limit")
    if not _valid_content(mime, data):
        raise HTTPException(415, "Guide file content does not match a supported type")
    name = secrets.token_hex(24) + extension
    final = safe_guide_path(name)
    temp = final.with_suffix(final.suffix + ".tmp")
    try:
        async with aiofiles.open(temp, "wb") as handle:
            await handle.write(data)
        os.replace(temp, final)
    finally:
        temp.unlink(missing_ok=True)
    raw_original = Path(upload.filename or "guide" + extension).name
    original = "".join(ch for ch in raw_original if ch.isprintable() and ch not in "\r\n\"")[:255] or "guide" + extension
    return final, mime, len(data), original

async def portal_user(request: Request, db: AsyncSession) -> ClientUser:
    user_id = portal_sessions.get(request.cookies.get("portal_token", ""))
    if not user_id:
        raise HTTPException(401, "Portal authentication required")
    user = (await db.execute(select(ClientUser).where(ClientUser.id == user_id, ClientUser.is_active == True))).scalars().first()
    if not user:
        raise HTTPException(401, "Portal authentication required")
    return user

async def guide_or_404(db: AsyncSession, guide_id: int) -> ClientGuide:
    guide = (await db.execute(select(ClientGuide).where(ClientGuide.id == guide_id))).scalars().first()
    if not guide:
        raise HTTPException(404, "Guide not found")
    return guide

async def assignment_ids(db: AsyncSession, guide_id: int) -> list[int]:
    rows = await db.execute(select(ClientGuideAssignment.client_id).where(ClientGuideAssignment.guide_id == guide_id))
    return list(rows.scalars().all())

def payload(guide: ClientGuide, clients: list[int] | None = None) -> dict:
    return {"id": guide.id, "title": guide.title, "description": guide.description, "category": guide.category,
            "original_file_name": guide.original_file_name, "mime_type": guide.mime_type, "file_size": guide.file_size,
            "visibility_mode": guide.visibility_mode, "client_ids": clients or [], "published": guide.published,
            "featured": guide.featured, "display_order": guide.display_order,
            "created_at": guide.created_at.isoformat() if guide.created_at else None,
            "updated_at": guide.updated_at.isoformat() if guide.updated_at else None,
            "preview_url": f"/api/admin/client-guides/{guide.id}/file", "download_url": f"/api/admin/client-guides/{guide.id}/file?download=true"}

class GuideUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=1000)
    category: str = Field(min_length=1, max_length=100)
    visibility_mode: Literal["all", "selected"]
    client_ids: list[int] = Field(default_factory=list, max_length=10000)
    published: bool = False
    featured: bool = False
    display_order: int = Field(default=0, ge=-100000, le=100000)

async def apply_metadata(db: AsyncSession, guide: ClientGuide, data: GuideUpdate) -> None:
    if data.visibility_mode == "selected" and not data.client_ids:
        raise HTTPException(400, "Select at least one client")
    existing = set((await db.execute(select(Client.id).where(Client.id.in_(set(data.client_ids))))).scalars().all()) if data.client_ids else set()
    if existing != set(data.client_ids):
        raise HTTPException(400, "One or more selected clients are invalid")
    for field in ("title", "description", "category", "visibility_mode", "published", "featured", "display_order"):
        setattr(guide, field, getattr(data, field))
    guide.updated_at = datetime.utcnow()
    await db.execute(delete(ClientGuideAssignment).where(ClientGuideAssignment.guide_id == guide.id))
    if data.visibility_mode == "selected":
        for client_id in sorted(existing):
            db.add(ClientGuideAssignment(guide_id=guide.id, client_id=client_id))

async def audit(db: AsyncSession, admin: dict, request: Request, action: str, guide_id: int) -> None:
    db.add(SecurityAuditEvent(administrator=admin.get("username"), action=action, reason=f"guide_id={guide_id}",
        ip_address=request.client.host if request.client else None, user_agent=(request.headers.get("user-agent") or "")[:500]))

@router.get("/api/admin/client-guides")
async def admin_list(admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    guides = (await db.execute(select(ClientGuide).order_by(ClientGuide.display_order, ClientGuide.updated_at.desc()))).scalars().all()
    return [payload(g, await assignment_ids(db, g.id)) for g in guides]

@router.get("/api/admin/client-guides/{guide_id}")
async def admin_get(guide_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    guide = await guide_or_404(db, guide_id)
    return payload(guide, await assignment_ids(db, guide.id))

@router.post("/api/admin/client-guides", status_code=201)
async def create_guide(request: Request, title: str = Form(...), description: str = Form(""), category: str = Form(...),
    visibility_mode: Literal["all", "selected"] = Form("all"), client_ids: str = Form(""), published: bool = Form(False),
    featured: bool = Form(False), display_order: int = Form(0), guide_file: UploadFile = File(...),
    admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    ids = [int(x) for x in client_ids.split(",") if x.strip().isdigit()]
    data = GuideUpdate(title=title, description=description, category=category, visibility_mode=visibility_mode,
        client_ids=ids, published=published, featured=featured, display_order=display_order)
    final, mime, size, original = await save_upload(guide_file)
    guide = ClientGuide(title=data.title, description=data.description, category=data.category, stored_file_name=final.name,
        original_file_name=original, mime_type=mime, file_size=size, visibility_mode=data.visibility_mode,
        published=data.published, featured=data.featured, display_order=data.display_order)
    db.add(guide)
    try:
        await db.flush(); await apply_metadata(db, guide, data); await audit(db, admin, request, "client_guide_created", guide.id); await db.commit()
    except Exception:
        await db.rollback(); final.unlink(missing_ok=True); raise
    return payload(guide, await assignment_ids(db, guide.id))

@router.put("/api/admin/client-guides/{guide_id}")
async def update_guide(guide_id: int, data: GuideUpdate, request: Request, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    guide = await guide_or_404(db, guide_id); was_published = guide.published
    await apply_metadata(db, guide, data)
    await audit(db, admin, request, "client_guide_published" if data.published != was_published else "client_guide_updated", guide.id)
    await db.commit(); return payload(guide, await assignment_ids(db, guide.id))

@router.post("/api/admin/client-guides/{guide_id}/file")
async def replace_file(guide_id: int, request: Request, guide_file: UploadFile = File(...), admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    guide = await guide_or_404(db, guide_id); old = guide.stored_file_name
    final, mime, size, original = await save_upload(guide_file)
    try:
        guide.stored_file_name, guide.original_file_name, guide.mime_type, guide.file_size = final.name, original, mime, size
        guide.updated_at = datetime.utcnow(); await audit(db, admin, request, "client_guide_file_replaced", guide.id); await db.commit()
    except Exception:
        await db.rollback(); final.unlink(missing_ok=True); raise
    try: safe_guide_path(old).unlink(missing_ok=True)
    except OSError: pass
    return payload(guide, await assignment_ids(db, guide.id))

@router.delete("/api/admin/client-guides/{guide_id}")
async def delete_guide(guide_id: int, request: Request, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    guide = await guide_or_404(db, guide_id); stored = guide.stored_file_name
    await audit(db, admin, request, "client_guide_deleted", guide.id); await db.delete(guide); await db.commit()
    try: safe_guide_path(stored).unlink(missing_ok=True)
    except OSError: pass
    return {"status": "deleted"}

async def file_response(guide: ClientGuide, download: bool):
    try: path = safe_guide_path(guide.stored_file_name)
    except ValueError: raise HTTPException(404, "Guide file not found")
    if not path.is_file() or path.is_symlink(): raise HTTPException(404, "Guide file not found")
    disposition = "attachment" if download else "inline"
    return FileResponse(path, media_type=guide.mime_type, filename=guide.original_file_name if download else None,
        headers={"Content-Disposition": f'{disposition}; filename="{guide.original_file_name.replace(chr(34), "")}"'})

@router.get("/api/admin/client-guides/{guide_id}/file")
async def admin_file(guide_id: int, download: bool = False, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await file_response(await guide_or_404(db, guide_id), download)

async def visible_guides(db: AsyncSession, client_id: int):
    assigned = select(ClientGuideAssignment.guide_id).where(ClientGuideAssignment.client_id == client_id)
    return (await db.execute(select(ClientGuide).where(ClientGuide.published == True,
        or_(ClientGuide.visibility_mode == "all", ClientGuide.id.in_(assigned))).order_by(ClientGuide.display_order, ClientGuide.updated_at.desc()))).scalars().all()

@router.get("/api/portal/guides")
async def client_list(request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db); guides = await visible_guides(db, user.client_id)
    return [{**payload(g), "preview_url": f"/api/portal/guides/{g.id}/file", "download_url": f"/api/portal/guides/{g.id}/file?download=true"} for g in guides]

@router.get("/api/portal/guides/featured")
async def client_featured(request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db); guides = await visible_guides(db, user.client_id)
    guide = next((g for g in guides if g.featured), None)
    return None if not guide else {**payload(guide), "open_url": f"/portal/guides#{guide.id}"}

@router.get("/api/portal/guides/{guide_id}")
async def client_get(guide_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db); guides = await visible_guides(db, user.client_id)
    guide = next((g for g in guides if g.id == guide_id), None)
    if not guide: raise HTTPException(404, "Guide not found")
    return payload(guide)

@router.get("/api/portal/guides/{guide_id}/file")
async def client_file(guide_id: int, request: Request, download: bool = False, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db); guides = await visible_guides(db, user.client_id)
    guide = next((g for g in guides if g.id == guide_id), None)
    if not guide: raise HTTPException(404, "Guide not found")
    return await file_response(guide, download)

@router.get("/portal/guides", response_class=HTMLResponse)
async def guides_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db); guides = await visible_guides(db, user.client_id)
    cards = "".join(f'''<article class="guide-card" id="{g.id}" role="button" tabindex="0" aria-label="Open {escape(g.title)}" data-guide-id="{g.id}" data-mime="{g.mime_type}" data-updated="{escape(g.updated_at.isoformat() if g.updated_at else '')}">
      <div class="preview">{f'<img src="/api/portal/guides/{g.id}/file" alt="Preview of {escape(g.title)}">' if g.mime_type.startswith('image/') else '<div class="pdf-mark" aria-hidden="true">PDF</div>'}</div>
      <div class="content"><div class="meta"><span>{escape(g.category)}</span><span class="new-badge">New</span></div><h2>{escape(g.title)}</h2><p>{escape(g.description)}</p><small>Updated {g.updated_at.strftime('%d %b %Y') if g.updated_at else 'recently'}</small>
      <button type="button" class="open-guide-action">Open Guide</button></div></article>''' for g in guides)
    if not cards: cards = '<div class="empty"><h2>No guides are currently published</h2><p>Helpful instructions will appear here when available.</p></div>'
    return HTMLResponse(f'''<!doctype html><html lang="en" data-theme-enabled><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><script src="/static/theme.js"></script><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="/static/theme.css"><title>Guides &amp; Help</title><style>
body{{background:#030712;color:#e5e7eb;font-family:Inter,system-ui;margin:0}}nav{{padding:16px;border-bottom:1px solid #ffffff1a;background:#111827dd}}nav a{{color:#c4b5fd;text-decoration:none;font-weight:700}}main{{max-width:1200px;margin:auto;padding:28px 18px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}}.guide-card,.empty{{background:#111827;border:1px solid #ffffff1a;border-radius:18px;overflow:hidden}}.guide-card{{cursor:pointer;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease}}.guide-card:hover{{transform:translateY(-2px);border-color:#8b5cf680;box-shadow:0 16px 34px #0006}}.guide-card:focus-visible{{outline:3px solid #a78bfa;outline-offset:3px;border-color:#a78bfa}}.preview{{height:220px;background:#0b1020;display:flex;align-items:center;justify-content:center;overflow:hidden}}.preview img{{width:100%;height:100%;object-fit:cover;object-position:top}}.pdf-mark{{font-size:34px;font-weight:800;color:#fca5a5}}.content{{padding:20px}}.content h2{{font-size:20px;margin:10px 0}}.content p{{color:#9ca3af;min-height:48px}}.meta{{display:flex;justify-content:space-between;color:#c4b5fd;font-size:12px;text-transform:uppercase;letter-spacing:.08em}}button,.download{{display:inline-flex;margin-top:16px;background:#7c3aed;color:white;border:0;border-radius:12px;padding:11px 15px;font-weight:700;text-decoration:none;cursor:pointer;transition:background .18s ease,transform .18s ease,box-shadow .18s ease}}.open-guide-action{{width:100%;justify-content:center;background:#7c3aed;box-shadow:0 8px 20px #7c3aed33}}.open-guide-action:hover{{background:#8b5cf6;transform:translateY(-1px)}}.open-guide-action:focus-visible,.viewer button:focus-visible,.download:focus-visible{{outline:3px solid #c4b5fd;outline-offset:3px}}.new-badge{{background:#2563eb;color:white;padding:2px 7px;border-radius:999px}}.new-badge.seen{{display:none}}.viewer{{position:fixed;inset:0;background:#030712ed;z-index:90;padding:18px;display:flex;flex-direction:column}}.viewer.hidden{{display:none}}.viewer-head{{display:flex;justify-content:flex-end;gap:10px}}.viewer-body{{overflow:auto;text-align:center;flex:1;margin-top:12px}}.viewer img{{max-width:none;width:auto;min-width:min(100%,900px);height:auto}}.viewer iframe{{width:100%;height:100%;border:0;background:white}}.empty{{padding:40px;text-align:center;grid-column:1/-1}}@media(max-width:640px){{.viewer{{padding:8px}}.preview{{height:180px}}}}
</style></head><body><nav><a href="/portal">← Dashboard</a></nav><main><h1 class="text-3xl font-bold text-white">Guides &amp; Help</h1><p class="mt-2 mb-7 text-gray-400">Step-by-step instructions for your Home Assistant and MyBeacon services.</p><div class="grid">{cards}</div></main><div id="viewer" class="viewer hidden" role="dialog" aria-modal="true"><div class="viewer-head"><a id="download" class="download" download>Download</a><button onclick="closeGuide()">Close</button></div><div id="viewer-body" class="viewer-body"></div></div><script>
const seenKey='mybeacon-guide-seen-v1';let seen=JSON.parse(localStorage.getItem(seenKey)||'{{}}');let opener=null;const cards=document.querySelectorAll('.guide-card');cards.forEach(card=>{{if(seen[card.dataset.guideId]===card.dataset.updated)card.querySelector('.new-badge').classList.add('seen');card.addEventListener('click',event=>{{if(event.target.closest('a'))return;activateCard(card)}});card.addEventListener('keydown',event=>{{if(event.target!==card)return;if(event.key==='Enter'||event.key===' '){{event.preventDefault();activateCard(card)}}}});card.querySelector('.open-guide-action').addEventListener('click',event=>{{event.stopPropagation();activateCard(card)}})}});function activateCard(card){{openGuide(card.dataset.guideId,card.dataset.mime,card)}}function openGuide(id,mime,card){{opener=card||document.activeElement;seen[id]=card.dataset.updated;localStorage.setItem(seenKey,JSON.stringify(seen));card.querySelector('.new-badge').classList.add('seen');const url='/api/portal/guides/'+id+'/file';document.getElementById('download').href=url+'?download=true';document.getElementById('viewer-body').innerHTML=mime==='application/pdf'?'<iframe title="Guide PDF" src="'+url+'"></iframe>':'<img alt="Guide" src="'+url+'">';const viewer=document.getElementById('viewer');viewer.classList.remove('hidden');viewer.querySelector('button').focus()}}function closeGuide(){{document.getElementById('viewer').classList.add('hidden');document.getElementById('viewer-body').textContent='';if(opener)opener.focus()}}document.addEventListener('keydown',event=>{{if(event.key==='Escape'&&!document.getElementById('viewer').classList.contains('hidden'))closeGuide()}});if(location.hash){{const card=document.getElementById(location.hash.slice(1));if(card)activateCard(card)}}
</script></body></html>''')
