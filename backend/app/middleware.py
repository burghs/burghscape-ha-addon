"""Authentication middleware for admin API routes."""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from admin_auth import verify_admin_token

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/health",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/agent/report",
    "/api/agent/status",
    "/api/agent/validate",
    "/api/tunnels/config",
    "/portal/login",
    "/portal/logout",
    "/portal",
    "/api/portal/auth/login",
    "/api/portal/users",
    "/api/portal/tickets",
}

# Prefixes that are public
PUBLIC_PREFIXES = (
    "/api/portal/",
    "/portal/",
)


class AdminAuthMiddleware(BaseHTTPMiddleware):
    """Require admin auth for all non-public API routes."""
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Check if exact path is public
        if path in PUBLIC_PATHS:
            response = await call_next(request)
            return response
        
        # Check if path starts with a public prefix
        if path.startswith(PUBLIC_PREFIXES):
            response = await call_next(request)
            return response
        
        # Allow static files and frontend assets
        if path.startswith(("/static/", "/assets/", "/favicon")):
            response = await call_next(request)
            return response
        
        # Allow files with extensions (static assets)
        if "." in path.split("/")[-1]:
            response = await call_next(request)
            return response
        
        # Require auth
        token = request.cookies.get("admin_token", "")
        if not token:
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:]
        
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )
        
        user = verify_admin_token(token)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )
        
        # Attach user to request state
        request.state.admin = user
        response = await call_next(request)
        return response
