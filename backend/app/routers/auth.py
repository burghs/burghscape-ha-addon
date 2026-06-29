"""Authentication endpoints for admin portal."""
from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel

from admin_auth import verify_admin_credentials, create_admin_token, get_current_admin

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login")
async def login(response: Response, request: LoginRequest):
    if not verify_admin_credentials(request.username, request.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_admin_token(request.username)
    
    # Set HTTP-only cookie for browser access
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        max_age=43200,  # 12 hours
        samesite="lax",
    )
    
    return TokenResponse(access_token=token)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("admin_token")
    return {"status": "logged_out"}


@router.get("/me")
async def get_current_user(admin: dict = Depends(get_current_admin)):
    return {"username": admin["username"], "role": admin["role"]}
