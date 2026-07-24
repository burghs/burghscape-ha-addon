"""Optional client TOTP enrollment, challenge, recovery, disable, and admin reset."""
from collections import defaultdict, deque
from datetime import datetime, timedelta
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_auth import get_current_admin
from database import get_db
from models import (ClientUser, SecurityAuditEvent, TwoFactorChallenge,
                    TwoFactorPendingEnrollment, TwoFactorRecoveryCode)
from routers.portal_state import portal_sessions
from two_factor_security import (decrypt_secret, encrypt_secret, hash_recovery_code,
                                 new_recovery_codes, new_totp_secret,
                                 provisioning_uri, qr_svg_data_uri, token_hash,
                                 verify_recovery_code, verify_totp)

router = APIRouter()
_attempts: dict[str, deque] = defaultdict(deque)


def _now() -> datetime:
    return datetime.utcnow()


def _limit(key: str, maximum: int, window_seconds: int = 300) -> None:
    now = _now().timestamp()
    bucket = _attempts[key]
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    if len(bucket) >= maximum:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    bucket.append(now)


def _request_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent", "")[:500] or None


async def _portal_user(request: Request, db: AsyncSession) -> ClientUser:
    token = request.cookies.get("portal_token", "")
    user_id = portal_sessions.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = (await db.execute(select(ClientUser).where(ClientUser.id == user_id, ClientUser.is_active == True))).scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    return user


async def _audit(db: AsyncSession, request: Request, user: ClientUser, action: str,
                 reason: str | None = None, administrator: str | None = None) -> None:
    ip, agent = _request_meta(request)
    db.add(SecurityAuditEvent(administrator=administrator, client_user_id=user.id,
                              client_id=user.client_id, action=action, reason=reason,
                              ip_address=ip, user_agent=agent))


async def _consume_recovery_code(db: AsyncSession, user_id: int, code: str) -> bool:
    rows = (await db.execute(select(TwoFactorRecoveryCode).where(
        TwoFactorRecoveryCode.client_user_id == user_id,
        TwoFactorRecoveryCode.used_at.is_(None),
    ).with_for_update())).scalars().all()
    for row in rows:
        if verify_recovery_code(code, row.code_hash):
            row.used_at = _now()
            await db.flush()
            return True
    return False


async def _factor_valid(db: AsyncSession, user: ClientUser, code: str, recovery: bool) -> bool:
    if recovery:
        return await _consume_recovery_code(db, user.id, code)
    if not user.encrypted_totp_secret:
        return False
    return verify_totp(decrypt_secret(user.encrypted_totp_secret), code)


class PasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=500)


class EnrollmentVerify(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class FactorRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)
    recovery_code: bool = False


class DisableRequest(FactorRequest):
    current_password: str = Field(min_length=1, max_length=500)
    confirm: bool


class RegenerateRequest(FactorRequest):
    current_password: str = Field(min_length=1, max_length=500)


class AdminResetRequest(BaseModel):
    confirm: bool
    reason: str = Field(min_length=5, max_length=1000)


@router.get("/api/portal/security/two-factor")
async def status(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _portal_user(request, db)
    unused = (await db.execute(select(TwoFactorRecoveryCode).where(
        TwoFactorRecoveryCode.client_user_id == user.id,
        TwoFactorRecoveryCode.used_at.is_(None),
    ))).scalars().all()
    return {"enabled": bool(user.two_factor_enabled),
            "enabled_at": user.two_factor_enabled_at.isoformat() if user.two_factor_enabled_at else None,
            "recovery_codes_remaining": len(unused)}


@router.post("/api/portal/security/two-factor/enroll")
async def start_enrollment(body: PasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _portal_user(request, db)
    from routers.portal_users import verify_password
    _limit(f"enroll-start:{user.id}", 5)
    if user.two_factor_enabled:
        raise HTTPException(status_code=409, detail="Two-factor authentication is already enabled")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Unable to start enrollment")
    await db.execute(delete(TwoFactorPendingEnrollment).where(TwoFactorPendingEnrollment.client_user_id == user.id))
    secret = new_totp_secret()
    db.add(TwoFactorPendingEnrollment(client_user_id=user.id, encrypted_secret=encrypt_secret(secret),
                                      expires_at=_now() + timedelta(minutes=10)))
    uri = provisioning_uri(secret, user.email)
    await _audit(db, request, user, "two_factor_enrollment_started")
    return {"manual_key": secret, "otpauth_uri": uri, "qr_code": qr_svg_data_uri(uri),
            "issuer": "MyBeacon by Burghscape", "expires_in_seconds": 600}


@router.post("/api/portal/security/two-factor/enroll/verify")
async def confirm_enrollment(body: EnrollmentVerify, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _portal_user(request, db)
    _limit(f"enroll-verify:{user.id}", 8)
    pending = (await db.execute(select(TwoFactorPendingEnrollment).where(
        TwoFactorPendingEnrollment.client_user_id == user.id).with_for_update())).scalars().first()
    if not pending or pending.expires_at <= _now():
        if pending:
            await db.delete(pending)
        raise HTTPException(status_code=400, detail="Enrollment expired. Start again.")
    secret = decrypt_secret(pending.encrypted_secret)
    if not verify_totp(secret, body.code):
        raise HTTPException(status_code=400, detail="The authenticator code is invalid")
    codes = new_recovery_codes()
    await db.execute(delete(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.client_user_id == user.id))
    for code in codes:
        db.add(TwoFactorRecoveryCode(client_user_id=user.id, code_hash=hash_recovery_code(code)))
    user.encrypted_totp_secret = encrypt_secret(secret)
    user.two_factor_enabled = True
    user.two_factor_enabled_at = _now()
    await db.delete(pending)
    await _audit(db, request, user, "two_factor_enabled")
    return {"enabled": True, "recovery_codes": codes}


@router.post("/api/portal/security/two-factor/enroll/cancel")
async def cancel_enrollment(request: Request, db: AsyncSession = Depends(get_db)):
    user = await _portal_user(request, db)
    await db.execute(delete(TwoFactorPendingEnrollment).where(TwoFactorPendingEnrollment.client_user_id == user.id))
    await _audit(db, request, user, "two_factor_enrollment_cancelled")
    return {"enabled": bool(user.two_factor_enabled)}


@router.post("/api/portal/security/two-factor/recovery-codes")
async def regenerate_codes(body: RegenerateRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _portal_user(request, db)
    from routers.portal_users import verify_password
    _limit(f"recovery-regenerate:{user.id}", 5)
    if not user.two_factor_enabled or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Unable to regenerate recovery codes")
    if not await _factor_valid(db, user, body.code, body.recovery_code):
        raise HTTPException(status_code=400, detail="Unable to regenerate recovery codes")
    codes = new_recovery_codes()
    await db.execute(delete(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.client_user_id == user.id))
    for code in codes:
        db.add(TwoFactorRecoveryCode(client_user_id=user.id, code_hash=hash_recovery_code(code)))
    await _audit(db, request, user, "two_factor_recovery_codes_regenerated")
    return {"recovery_codes": codes}


@router.post("/api/portal/security/two-factor/disable")
async def disable(body: DisableRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await _portal_user(request, db)
    from routers.portal_users import verify_password
    _limit(f"disable:{user.id}", 6)
    if not body.confirm or not user.two_factor_enabled or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Unable to disable two-factor authentication")
    if not await _factor_valid(db, user, body.code, body.recovery_code):
        raise HTTPException(status_code=400, detail="Unable to disable two-factor authentication")
    user.two_factor_enabled = False
    user.encrypted_totp_secret = None
    user.two_factor_enabled_at = None
    await db.execute(delete(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.client_user_id == user.id))
    await db.execute(delete(TwoFactorPendingEnrollment).where(TwoFactorPendingEnrollment.client_user_id == user.id))
    await db.execute(delete(TwoFactorChallenge).where(TwoFactorChallenge.client_user_id == user.id,
                                                       TwoFactorChallenge.used_at.is_(None)))
    await _audit(db, request, user, "two_factor_disabled")
    return {"enabled": False}


@router.post("/api/portal/auth/two-factor/verify")
async def verify_challenge(body: FactorRequest, request: Request, response: Response,
                           db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get("portal_2fa_challenge", "")
    factor_kind = "recovery" if body.recovery_code else "totp"
    _limit(f"challenge:{factor_kind}:{token_hash(raw) if raw else 'missing'}", 8)
    challenge = (await db.execute(select(TwoFactorChallenge).where(
        TwoFactorChallenge.token_hash == token_hash(raw),
    ).with_for_update())).scalars().first() if raw else None
    if not challenge or challenge.used_at or challenge.invalidated_at or challenge.expires_at <= _now():
        raise HTTPException(status_code=401, detail="Verification expired. Sign in again.")
    user = (await db.execute(select(ClientUser).where(ClientUser.id == challenge.client_user_id,
                                                       ClientUser.is_active == True))).scalars().first()
    if not user or not user.two_factor_enabled or not user.encrypted_totp_secret:
        challenge.invalidated_at = _now()
        raise HTTPException(status_code=401, detail="Verification expired. Sign in again.")
    challenge.attempts += 1
    if challenge.attempts > 8 or not await _factor_valid(db, user, body.code, body.recovery_code):
        if challenge.attempts >= 8:
            challenge.invalidated_at = _now()
        raise HTTPException(status_code=401, detail="The verification code is invalid")
    challenge.used_at = _now()
    other_challenges = (await db.execute(select(TwoFactorChallenge).where(
        TwoFactorChallenge.client_user_id == user.id,
        TwoFactorChallenge.id != challenge.id,
        TwoFactorChallenge.used_at.is_(None),
        TwoFactorChallenge.invalidated_at.is_(None),
    ).with_for_update())).scalars().all()
    for other in other_challenges:
        other.invalidated_at = _now()
    session_token = secrets.token_urlsafe(48)
    portal_sessions[session_token] = user.id
    user.last_login = _now()
    response.set_cookie("portal_token", session_token, httponly=True, secure=True,
                        samesite="lax", path="/")
    response.delete_cookie("portal_2fa_challenge", path="/")
    await _audit(db, request, user, "two_factor_login_verified")
    return {"verified": True, "force_password_change": bool(user.force_password_change)}


@router.get("/api/portal/admin/security-audit")
async def admin_security_audit(admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SecurityAuditEvent).where(
        SecurityAuditEvent.action == "two_factor_admin_reset"
    ).order_by(SecurityAuditEvent.created_at.desc()).limit(100))).scalars().all()
    return [{
        "id": row.id, "administrator": row.administrator,
        "client_user_id": row.client_user_id, "client_id": row.client_id,
        "action": row.action, "reason": row.reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row in rows]


@router.post("/api/portal/admin/portal-users/{user_id}/two-factor/reset")
async def admin_reset(user_id: int, body: AdminResetRequest, request: Request,
                      admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    _limit(f"admin-reset:{admin['username']}:{_request_meta(request)[0]}", 10, 600)
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Confirmation is required")
    user = (await db.execute(select(ClientUser).where(ClientUser.id == user_id).with_for_update())).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Portal user not found")
    was_enabled = bool(user.two_factor_enabled)
    user.two_factor_enabled = False
    user.encrypted_totp_secret = None
    user.two_factor_enabled_at = None
    await db.execute(delete(TwoFactorRecoveryCode).where(TwoFactorRecoveryCode.client_user_id == user.id))
    await db.execute(delete(TwoFactorPendingEnrollment).where(TwoFactorPendingEnrollment.client_user_id == user.id))
    await db.execute(delete(TwoFactorChallenge).where(TwoFactorChallenge.client_user_id == user.id,
                                                       TwoFactorChallenge.used_at.is_(None)))
    await _audit(db, request, user, "two_factor_admin_reset", body.reason, admin["username"])
    return {"reset": True, "was_enabled": was_enabled, "audit_recorded": True}


TWO_FACTOR_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Two-factor verification · MyBeacon</title><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="/static/theme.css"></head><body class="min-h-screen bg-slate-950 text-white grid place-items-center p-4"><main class="w-full max-w-md rounded-2xl border border-purple-400/20 bg-slate-900 p-6 shadow-2xl"><h1 class="text-2xl font-bold">Two-factor verification</h1><p class="mt-2 text-sm text-slate-300">Enter the current code from your authenticator app.</p><form id="factor-form" class="mt-6 space-y-4"><label class="block"><span class="text-sm">Verification code</span><input id="factor-code" inputmode="numeric" autocomplete="one-time-code" maxlength="32" required class="mt-2 w-full rounded-xl border border-white/20 bg-slate-950 px-4 py-3 text-lg tracking-widest"></label><label class="flex min-h-11 items-center gap-3"><input id="factor-recovery" type="checkbox"><span>Use a recovery code</span></label><p id="factor-error" role="alert" class="hidden text-sm text-red-300"></p><button class="w-full min-h-12 rounded-xl bg-purple-600 font-semibold">Verify and continue</button><a href="/portal/two-factor/cancel" class="block min-h-11 py-3 text-center text-slate-300">Cancel and return to login</a></form></main><script>document.getElementById('factor-form').addEventListener('submit',async(e)=>{e.preventDefault();const error=document.getElementById('factor-error');error.classList.add('hidden');const response=await fetch('/api/portal/auth/two-factor/verify',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:document.getElementById('factor-code').value,recovery_code:document.getElementById('factor-recovery').checked})});const data=await response.json();if(response.ok){location.replace(data.force_password_change?'/portal/change-password':'/portal');return}error.textContent=data.detail||'Verification failed';error.classList.remove('hidden')});</script></body></html>"""


@router.get("/portal/two-factor/cancel")
async def cancel_challenge(request: Request, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get("portal_2fa_challenge", "")
    if raw:
        challenge = (await db.execute(select(TwoFactorChallenge).where(
            TwoFactorChallenge.token_hash == token_hash(raw),
            TwoFactorChallenge.used_at.is_(None),
        ))).scalars().first()
        if challenge:
            challenge.invalidated_at = _now()
    response = HTMLResponse(status_code=302, headers={"Location": "/portal/login"})
    response.delete_cookie("portal_2fa_challenge", path="/")
    return response


@router.get("/portal/two-factor", response_class=HTMLResponse)
async def challenge_page(request: Request):
    if not request.cookies.get("portal_2fa_challenge"):
        return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})
    return HTMLResponse(TWO_FACTOR_PAGE, headers={"Cache-Control": "no-store"})

SECURITY_PAGE = """<!doctype html><html lang="en" data-theme-enabled><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Account Security · MyBeacon</title><script src="/static/theme.js"></script><script src="https://cdn.tailwindcss.com"></script><link rel="stylesheet" href="/static/theme.css"></head><body class="min-h-screen bg-slate-950 text-white"><nav class="border-b border-white/10 p-4"><div class="mx-auto flex max-w-3xl items-center justify-between"><a href="/portal" class="font-semibold text-purple-300">← Client Portal</a><span>Account Security</span></div></nav><main class="mx-auto max-w-3xl p-4 py-8"><section class="rounded-2xl border border-white/10 bg-slate-900 p-5 sm:p-7"><h1 class="text-2xl font-bold">Authenticator app</h1><p class="mt-2 text-slate-300">Optional two-factor authentication adds a current authenticator code after your password.</p><p class="mt-4">Status: <strong id="status">Loading…</strong></p><p id="enabled-date" class="mt-1 text-sm text-slate-400"></p><p id="remaining" class="mt-1 text-sm text-slate-400"></p><button id="retry-status" type="button" class="mt-3 hidden min-h-11 rounded-xl border border-white/20 px-5">Retry</button><div id="enable-panel" class="mt-6 hidden"><label class="block text-sm">Current password<input id="enable-password" type="password" autocomplete="current-password" class="mt-2 w-full rounded-xl border border-white/20 bg-slate-950 p-3"></label><button id="enable" class="mt-3 min-h-11 rounded-xl bg-purple-600 px-5 font-semibold">Enable authenticator app</button></div><div id="setup" class="mt-6 hidden"><h2 class="text-xl font-semibold">Scan this locally generated QR code</h2><img id="qr" class="mt-4 w-full max-w-64 rounded-xl bg-white p-3" alt="Authenticator setup QR code"><p class="mt-4 text-sm">Manual setup key</p><code id="manual" class="mt-2 block break-all rounded-lg bg-black/30 p-3"></code><label class="mt-4 block text-sm">Current six-digit code<input id="setup-code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" class="mt-2 w-full rounded-xl border border-white/20 bg-slate-950 p-3"></label><div class="mt-3 flex flex-wrap gap-3"><button id="verify" class="min-h-11 rounded-xl bg-purple-600 px-5 font-semibold">Verify and enable</button><button id="cancel" class="min-h-11 rounded-xl border border-white/20 px-5">Cancel</button></div></div><div id="codes" class="mt-6 hidden"><h2 class="text-xl font-semibold">Save your recovery codes</h2><p class="mt-2 text-amber-200">These codes are displayed once. Store them somewhere safe.</p><pre id="code-list" class="mt-3 overflow-x-auto rounded-xl bg-black/30 p-4"></pre><label class="mt-4 flex min-h-11 items-center gap-3"><input id="saved" type="checkbox"><span>I have saved these recovery codes</span></label><button id="finish" disabled class="mt-3 min-h-11 rounded-xl bg-purple-600 px-5 font-semibold disabled:opacity-40">Finish</button></div><div id="disable-panel" class="mt-6 hidden border-t border-white/10 pt-6"><h2 class="text-xl font-semibold">Manage two-factor authentication</h2><h3 class="mt-5 text-lg font-semibold">Disable two-factor authentication</h3><p class="mt-2 text-sm text-slate-300">Requires your current password and an authenticator or recovery code.</p><input id="disable-password" type="password" autocomplete="current-password" placeholder="Current password" class="mt-3 w-full rounded-xl border border-white/20 bg-slate-950 p-3"><input id="disable-code" placeholder="Authenticator or recovery code" class="mt-3 w-full rounded-xl border border-white/20 bg-slate-950 p-3"><label class="mt-3 flex min-h-11 items-center gap-3"><input id="disable-recovery" type="checkbox"><span>Use recovery code</span></label><div class="mt-3 flex flex-wrap gap-3"><button id="regenerate" class="min-h-11 rounded-xl border border-white/20 px-5">Regenerate recovery codes</button><button id="disable" class="min-h-11 rounded-xl bg-red-700 px-5 font-semibold">Disable two-factor authentication</button></div></div><p id="message" role="status" class="mt-5 text-sm"></p></section></main><script>const q=id=>document.getElementById(id),message=(text,error=false)=>{q('message').textContent=text;q('message').className='mt-5 text-sm '+(error?'text-red-300':'text-emerald-300')};async function load(){const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8000);q('status').textContent='Loading…';q('retry-status').classList.add('hidden');q('enable-panel').classList.add('hidden');q('disable-panel').classList.add('hidden');q('enabled-date').textContent='';q('remaining').textContent='';try{const r=await fetch('/api/portal/security/two-factor',{credentials:'include',cache:'no-store',signal:controller.signal});if(!r.ok)throw new Error('status request failed');const d=await r.json();if(typeof d.enabled!=='boolean'||typeof d.recovery_codes_remaining!=='number'||(d.enabled_at!==null&&typeof d.enabled_at!=='string'))throw new Error('invalid status response');q('status').textContent=d.enabled?'Enabled':'Disabled';q('enable-panel').classList.toggle('hidden',d.enabled);q('disable-panel').classList.toggle('hidden',!d.enabled);q('enabled-date').textContent=d.enabled&&d.enabled_at?'Enabled '+new Date(d.enabled_at).toLocaleDateString():'';q('remaining').textContent=d.enabled?d.recovery_codes_remaining+' unused recovery code'+(d.recovery_codes_remaining===1?'':'s')+' remain':''}catch(error){q('status').textContent='Unable to load two-factor status';q('retry-status').classList.remove('hidden')}finally{clearTimeout(timeout)}}q('retry-status').onclick=load;q('enable').onclick=async()=>{const r=await fetch('/api/portal/security/two-factor/enroll',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:q('enable-password').value})}),d=await r.json();if(!r.ok){message(d.detail||'Unable to start enrollment',true);return}q('qr').src=d.qr_code;q('manual').textContent=d.manual_key;q('setup').classList.remove('hidden');q('enable-panel').classList.add('hidden')};q('verify').onclick=async()=>{const r=await fetch('/api/portal/security/two-factor/enroll/verify',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:q('setup-code').value})}),d=await r.json();if(!r.ok){message(d.detail||'Verification failed',true);return}q('setup').classList.add('hidden');q('codes').classList.remove('hidden');q('code-list').textContent=d.recovery_codes.join('\\n');q('manual').textContent=''};q('saved').onchange=()=>q('finish').disabled=!q('saved').checked;q('finish').onclick=()=>{q('codes').classList.add('hidden');message('Two-factor authentication enabled.');load()};q('cancel').onclick=async()=>{await fetch('/api/portal/security/two-factor/enroll/cancel',{method:'POST',credentials:'include'});q('manual').textContent='';q('qr').removeAttribute('src');q('setup').classList.add('hidden');load()};q('regenerate').onclick=async()=>{if(!confirm('Invalidate all previous recovery codes and generate new ones?'))return;const r=await fetch('/api/portal/security/two-factor/recovery-codes',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:q('disable-password').value,code:q('disable-code').value,recovery_code:q('disable-recovery').checked})}),d=await r.json();if(!r.ok){message(d.detail||'Unable to regenerate recovery codes',true);return}q('codes').classList.remove('hidden');q('code-list').textContent=d.recovery_codes.join('\\n');q('saved').checked=false;q('finish').disabled=true;message('Previous recovery codes are now invalid. Save the new codes.')};q('disable').onclick=async()=>{if(!confirm('Disable two-factor authentication?'))return;const r=await fetch('/api/portal/security/two-factor/disable',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({current_password:q('disable-password').value,code:q('disable-code').value,recovery_code:q('disable-recovery').checked,confirm:true})}),d=await r.json();message(r.ok?'Two-factor authentication disabled.':d.detail||'Unable to disable',!r.ok);if(r.ok)load()};load();</script></body></html>"""


@router.get("/portal/security", response_class=HTMLResponse)
async def security_page(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        await _portal_user(request, db)
    except HTTPException:
        return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})
    return HTMLResponse(SECURITY_PAGE, headers={"Cache-Control": "no-store"})
