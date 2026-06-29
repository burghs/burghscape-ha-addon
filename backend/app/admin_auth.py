"""Admin authentication - JWT-based auth for the management portal."""
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import secrets
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from jose import JWTError, jwt

from config import get_settings

settings = get_settings()

# --- Password hashing ---

def _hash_password(password: str, salt: str = "") -> str:
    """Hash password with salt using SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hash_obj}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash."""
    salt, _ = stored.split(":", 1)
    return _hash_password(password, salt) == stored


# --- Admin users store ---
# In production this would be in a database table
ADMIN_USERS = {
    "admin": {
        "password_hash": _hash_password("Beacon2026!", "burghscape_salt_2026"),
        "role": "superadmin",
    }
}


# --- JWT Token management ---

def create_admin_token(username: str) -> str:
    """Create a JWT token for admin user."""
    expire = datetime.utcnow() + timedelta(hours=12)
    payload = {
        "sub": username,
        "exp": expire,
        "type": "admin",
        "role": ADMIN_USERS[username]["role"],
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_admin_token(token: str) -> Optional[dict]:
    """Verify and decode admin JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "admin":
            return None
        username = payload.get("sub")
        if username not in ADMIN_USERS:
            return None
        return {"username": username, "role": payload.get("role")}
    except JWTError:
        return None


async def get_current_admin(request: Request) -> dict:
    """Dependency to verify admin authentication from cookie or header."""
    token = request.cookies.get("admin_token", "")
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = verify_admin_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user


def verify_admin_credentials(username: str, password: str) -> bool:
    """Verify admin username/password."""
    if username not in ADMIN_USERS:
        return False
    return _verify_password(password, ADMIN_USERS[username]["password_hash"])


# --- Password change router ---

admin_auth_router = APIRouter()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateAdminRequest(BaseModel):
    username: str
    password: str


@admin_auth_router.post("/password")
async def change_password(
    req: ChangePasswordRequest,
    admin: dict = Depends(get_current_admin),
):
    """Change admin password."""
    username = admin["username"]
    
    if username not in ADMIN_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not _verify_password(req.current_password, ADMIN_USERS[username]["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    ADMIN_USERS[username]["password_hash"] = _hash_password(req.new_password)
    
    return {"status": "password_changed"}


@admin_auth_router.post("/users")
async def create_admin_user(
    req: CreateAdminRequest,
    admin: dict = Depends(get_current_admin),
):
    """Create a new admin user (superadmin only)."""
    if admin["role"] != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin access required")
    
    if req.username in ADMIN_USERS:
        raise HTTPException(status_code=400, detail="User already exists")
    
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    ADMIN_USERS[req.username] = {
        "password_hash": _hash_password(req.password),
        "role": "admin",
    }
    
    return {"status": "created", "username": req.username}


@admin_auth_router.get("/users")
async def list_admin_users(admin: dict = Depends(get_current_admin)):
    """List admin users."""
    return {
        "users": [
            {"username": k, "role": v["role"]}
            for k, v in ADMIN_USERS.items()
        ]
    }
