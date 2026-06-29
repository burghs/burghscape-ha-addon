"""Client user management and portal authentication."""
import secrets
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, async_session
from models import ClientUser, Client, SupportTicket

router = APIRouter()


# --- Pydantic Schemas ---

class PortalLogin(BaseModel):
    email: str
    password: str

class PortalUserCreate(BaseModel):
    name: str
    email: str
    password: str
    role: str = "viewer"  # admin, viewer

class PortalUserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: Optional[str]


def hash_password(password: str) -> str:
    """Hash password with salt."""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256(f"{salt}{password}".encode())
    return f"{salt}:{hash_obj.hexdigest()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash."""
    salt, hash_val = stored.split(":")
    hash_obj = hashlib.sha256(f"{salt}{password}".encode())
    return hash_obj.hexdigest() == hash_val


def generate_session_token() -> str:
    """Generate a session token."""
    return secrets.token_urlsafe(48)


# Use shared session store
from routers.portal_state import portal_sessions as portal_tokens


async def verify_portal_token(token: str, db: AsyncSession) -> Optional[ClientUser]:
    """Verify a portal session token and return the user."""
    user_id = portal_tokens.get(token)
    if not user_id:
        return None
    
    result = await db.execute(select(ClientUser).where(ClientUser.id == user_id))
    return result.scalars().first()


# --- Auth Endpoints ---

@router.post("/auth/login")
async def portal_login(login: PortalLogin, db: AsyncSession = Depends(get_db)):
    """Login to client portal."""
    result = await db.execute(
        select(ClientUser).where(
            ClientUser.email == login.email,
            ClientUser.is_active == True
        )
    )
    user = result.scalars().first()
    
    if not user or not verify_password(login.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate session token
    token = generate_session_token()
    portal_tokens[token] = user.id
    user.last_login = datetime.now()
    await db.flush()
    
    return {
        "token": token,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "client_id": user.client_id,
            "force_password_change": user.force_password_change,
        }
    }


# --- User Management Endpoints ---

@router.get("/users", response_model=List[PortalUserResponse])
async def list_portal_users(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """List users for a client."""
    user = await verify_portal_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    result = await db.execute(
        select(ClientUser).where(ClientUser.client_id == user.client_id)
    )
    users = result.scalars().all()
    
    return [
        PortalUserResponse(
            id=u.id,
            name=u.name,
            email=u.email,
            role=u.role,
            created_at=u.created_at.isoformat() if u.created_at else None,
        )
        for u in users
    ]


@router.post("/users", response_model=PortalUserResponse)
async def create_portal_user(
    new_user: PortalUserCreate,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Add a new portal user (admin only)."""
    requesting_user = await verify_portal_token(token, db)
    if not requesting_user:
        raise HTTPException(status_code=401, detail="Invalid session")
    if requesting_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check email uniqueness
    existing = await db.execute(
        select(ClientUser).where(ClientUser.email == new_user.email)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = ClientUser(
        client_id=requesting_user.client_id,
        name=new_user.name,
        email=new_user.email,
        password_hash=hash_password(new_user.password),
        role=new_user.role,
    )
    db.add(user)
    await db.flush()
    
    return PortalUserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.delete("/users/{user_id}")
async def delete_portal_user(
    user_id: int,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove a portal user (admin only)."""
    requesting_user = await verify_portal_token(token, db)
    if not requesting_user:
        raise HTTPException(status_code=401, detail="Invalid session")
    if requesting_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.execute(
        select(ClientUser).where(
            ClientUser.id == user_id,
            ClientUser.client_id == requesting_user.client_id
        )
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.flush()
    
    return {"status": "deleted", "user_id": user_id}


# --- Portal Ticket Endpoints ---

@router.post("/tickets")
async def create_portal_ticket(
    ticket: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a support ticket from the portal."""
    token = request.cookies.get("portal_token", "")
    user = await verify_portal_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    new_ticket = SupportTicket(
        client_id=user.client_id,
        title=ticket.get("title", ""),
        description=ticket.get("description", ""),
        priority=ticket.get("priority", "normal"),
        status="open",
        hours_used=0.0,
    )
    db.add(new_ticket)
    await db.flush()
    
    return {"status": "created", "ticket_id": new_ticket.id}


# --- Admin endpoints (superadmin manages all portal users) ---

class AdminPortalUserCreate(BaseModel):
    client_id: int
    name: str
    email: str
    password: str
    role: str = "viewer"

class AdminPortalUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/admin/portal-users")
async def admin_list_portal_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """List all portal users across all clients (admin only)."""
    token = request.cookies.get("admin_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    from admin_auth import verify_admin_token as verify_token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    result = await db.execute(
        select(ClientUser, Client)
        .join(Client, ClientUser.client_id == Client.id)
        .order_by(Client.name, ClientUser.name)
    )
    rows = result.all()
    
    return [
        {
            "id": u.id,
            "client_id": u.client_id,
            "client_name": c.name,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "force_password_change": u.force_password_change,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
        }
        for u, c in rows
    ]


@router.post("/admin/portal-users")
async def admin_create_portal_user(
    user: AdminPortalUserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a portal user for any client (admin only)."""
    token = request.cookies.get("admin_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    from admin_auth import verify_admin_token as verify_token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    client_result = await db.execute(select(Client).where(Client.id == user.client_id))
    if not client_result.scalars().first():
        raise HTTPException(status_code=404, detail="Client not found")
    
    existing = await db.execute(
        select(ClientUser).where(ClientUser.email == user.email)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = ClientUser(
        client_id=user.client_id,
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role=user.role,
    )
    db.add(new_user)
    await db.flush()
    
    return {
        "id": new_user.id,
        "client_id": new_user.client_id,
        "name": new_user.name,
        "email": new_user.email,
        "role": new_user.role,
        "is_active": new_user.is_active,
        "created_at": new_user.created_at.isoformat() if new_user.created_at else None,
    }


@router.put("/admin/portal-users/{user_id}")
async def admin_update_portal_user(
    user_id: int,
    user_update: AdminPortalUserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update a portal user (admin only)."""
    token = request.cookies.get("admin_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    from admin_auth import verify_admin_token as verify_token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    result = await db.execute(select(ClientUser).where(ClientUser.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_update.name is not None:
        user.name = user_update.name
    if user_update.email is not None:
        existing = await db.execute(
            select(ClientUser).where(
                ClientUser.email == user_update.email,
                ClientUser.id != user_id
            )
        )
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = user_update.email
    if user_update.password:
        user.password_hash = hash_password(user_update.password)
    if user_update.role is not None:
        user.role = user_update.role
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    
    await db.flush()
    
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }


@router.delete("/admin/portal-users/{user_id}")
async def admin_delete_portal_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Delete a portal user (admin only)."""
    token = request.cookies.get("admin_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    from admin_auth import verify_admin_token as verify_token
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    result = await db.execute(select(ClientUser).where(ClientUser.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.flush()
    
    return {"status": "deleted", "user_id": user_id}


# --- Portal user self-service password change ---

class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
async def portal_change_password(
    pw_change: PasswordChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Allow a logged-in portal user to change their own password."""
    token = request.cookies.get("portal_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user = await verify_portal_token(token, db)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    if not verify_password(pw_change.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    if len(pw_change.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    user.password_hash = hash_password(pw_change.new_password)
    user.force_password_change = False
    await db.flush()
    
    return {"status": "password_changed"}


# --- Password Reset Tokens (in-memory, use Redis/DB in production) ---
password_reset_tokens: dict = {}  # token -> {"user_id": int, "expires": datetime}

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    email: str
    token: str
    new_password: str


@router.post("/auth/forgot-password")
async def forgot_password(req: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """Request a password reset token."""
    result = await db.execute(
        select(ClientUser).where(
            ClientUser.email == req.email,
            ClientUser.is_active == True
        )
    )
    user = result.scalars().first()
    
    if not user:
        # Don't reveal if email exists
        return {"message": "If that email is registered, a reset code has been sent."}
    
    # Generate reset token (6-char alphanumeric, easy to type)
    import string
    reset_token = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    password_reset_tokens[reset_token] = {
        "user_id": user.id,
        "expires": datetime.now() + timedelta(hours=1),
    }
    
    # Get client for portal URL
    from models import Client
    client_result = await db.execute(select(Client).where(Client.id == user.client_id))
    client = client_result.scalars().first()
    portal_url = f"https://{client.subdomain}.mybeacon.co.za" if client else "https://client.mybeacon.co.za"
    
    # Send reset email
    from email_service import send_password_reset_email
    send_password_reset_email(user.email, user.name, reset_token, portal_url)
    
    return {"message": "If that email is registered, a reset code has been sent.", "debug_token": reset_token}


@router.post("/auth/reset-password")
async def reset_password(confirm: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    """Reset password using token."""
    stored = password_reset_tokens.get(confirm.token)
    if not stored:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    
    if datetime.now() > stored["expires"]:
        del password_reset_tokens[confirm.token]
        raise HTTPException(status_code=400, detail="Reset code has expired")
    
    result = await db.execute(
        select(ClientUser).where(
            ClientUser.id == stored["user_id"],
            ClientUser.email == confirm.email,
            ClientUser.is_active == True
        )
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset request")
    
    if len(confirm.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    user.password_hash = hash_password(confirm.new_password)
    user.force_password_change = False  # Clear flag since they set a new password
    await db.flush()
    
    # Invalidate token
    del password_reset_tokens[confirm.token]
    
    return {"status": "password_reset", "message": "Password has been reset. You can now log in."}

