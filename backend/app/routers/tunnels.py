"""Cloudflare Tunnel management endpoints."""
from datetime import datetime
import os
import httpx
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Client, SubscriptionToken

router = APIRouter()

CF_API_BASE = "https://api.cloudflare.com/client/v4"
CF_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CF_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CF_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID", "")
CF_DOMAIN = os.getenv("CLOUDFLARE_DOMAIN", "mybeacon.co.za")


class TunnelCreate(BaseModel):
    client_id: int
    subdomain: str


class TunnelInfo(BaseModel):
    tunnel_id: Optional[str]
    tunnel_token: Optional[str]
    hostname: Optional[str]
    status: str
    remote_access_url: Optional[str]


class TunnelConfig(BaseModel):
    """Config returned to the HA add-on for cloudflared."""
    tunnel_id: str
    tunnel_token: str
    hostname: str
    account_tag: str


async def delete_existing_cname(http: httpx.AsyncClient, subdomain: str):
    """Delete any existing CNAME records for a subdomain."""
    hostname = f"{subdomain}.{CF_DOMAIN}"
    dns_resp = await http.get(
        f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records",
        params={"name": hostname, "type": "CNAME"},
        headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
    )
    if dns_resp.status_code == 200:
        for record in dns_resp.json().get("result", []):
            await http.delete(
                f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records/{record['id']}",
                headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
            )


async def create_cname_record(http: httpx.AsyncClient, subdomain: str, tunnel_id: str):
    """Create CNAME record pointing subdomain to the tunnel."""
    # First delete any existing CNAME to avoid conflicts
    await delete_existing_cname(http, subdomain)
    
    resp = await http.post(
        f"{CF_API_BASE}/zones/{CF_ZONE_ID}/dns_records",
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "type": "CNAME",
            "name": subdomain,
            "content": f"{tunnel_id}.cfargotunnel.com",
            "proxied": True,
            "comment": f"Burghscape HA tunnel for {subdomain}",
        },
    )
    return resp.status_code == 200 and resp.json().get("success", False)


async def disable_cloudflare_optimizations(http: httpx.AsyncClient):
    """Disable Auto Minify and Rocket Loader for the zone to prevent HA frontend breakage."""
    settings = {
        "minify": {"value": {"css": "off", "html": "off", "js": "off"}},
        "rocket_loader": {"value": "off"},
        "always_online": {"value": "on"},
        "browser_cache_ttl": {"value": 14400},
    }
    for setting, payload in settings.items():
        try:
            await http.patch(
                f"{CF_API_BASE}/zones/{CF_ZONE_ID}/settings/{setting}",
                headers={
                    "Authorization": f"Bearer {CF_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception:
            pass  # Non-critical, continue if any setting fails


@router.get("/health")
async def tunnel_health():
    return {
        "status": "healthy" if CF_API_TOKEN else "not_configured",
        "service": "cloudflare-tunnel-manager",
        "domain": CF_DOMAIN,
        "account_id": CF_ACCOUNT_ID[:8] + "..." if CF_ACCOUNT_ID else "not_set",
        "zone_id": CF_ZONE_ID[:8] + "..." if CF_ZONE_ID else "not_set",
    }


@router.post("/create", response_model=TunnelInfo)
async def create_tunnel(tunnel: TunnelCreate, db: AsyncSession = Depends(get_db)):
    """Create a Cloudflare tunnel for a client."""
    if not CF_API_TOKEN or not CF_ACCOUNT_ID or not CF_ZONE_ID:
        raise HTTPException(status_code=500, detail="Cloudflare API credentials not configured")

    # Get client
    result = await db.execute(select(Client).where(Client.id == tunnel.client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    subdomain = tunnel.subdomain or client.subdomain
    hostname = f"{subdomain}.{CF_DOMAIN}"

    # Check if tunnel already exists
    if client.cloudflare_tunnel_id:
        raise HTTPException(status_code=400, detail=f"Tunnel already exists (id: {client.cloudflare_tunnel_id[:8]}...)")

    async with httpx.AsyncClient() as http:
        # 1. Create tunnel
        resp = await http.post(
            f"{CF_API_BASE}/accounts/{CF_ACCOUNT_ID}/cfd_tunnel",
            headers={
                "Authorization": f"Bearer {CF_API_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "name": f"mybeacon-{subdomain}",
                "config_src": "cloudflare",
            },
        )

        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"CF API error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if not data.get("success"):
            raise HTTPException(status_code=500, detail=f"Cloudflare error: {data.get('errors', [])}")

        tunnel_id = data["result"]["id"]
        tunnel_token = data["result"]["token"]

        # 2. Create CNAME DNS record (deletes existing first)
        dns_ok = await create_cname_record(http, subdomain, tunnel_id)
        
        # 3. Disable Cloudflare optimizations that break HA frontend
        await disable_cloudflare_optimizations(http)

    # Save to DB
    client.cloudflare_tunnel_id = tunnel_id
    client.cloudflare_tunnel_token = tunnel_token
    await db.flush()
    await db.refresh(client)

    return TunnelInfo(
        tunnel_id=tunnel_id,
        tunnel_token=tunnel_token,
        hostname=hostname,
        status="active",
        remote_access_url=f"https://{hostname}",
    )


@router.get("/config")
async def get_tunnel_config_for_addon(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Return tunnel config for the HA add-on.
    Add-on sends subscription token in Authorization header.
    If no tunnel exists yet, create one automatically.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token_str = authorization.replace("Bearer ", "")

    # Look up client by token (join to avoid lazy load issues)
    result = await db.execute(
        select(SubscriptionToken)
        .options(selectinload(SubscriptionToken.client))
        .where(
            SubscriptionToken.token == token_str,
            SubscriptionToken.is_active == True,
        )
    )
    token_obj = result.unique().scalars().first()
    if not token_obj:
        raise HTTPException(status_code=401, detail="Invalid or inactive subscription token")

    client = token_obj.client
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    subdomain = client.subdomain
    hostname = f"{subdomain}.{CF_DOMAIN}"

    # If no tunnel yet, create one
    if not client.cloudflare_tunnel_id:
        if not CF_API_TOKEN or not CF_ACCOUNT_ID or not CF_ZONE_ID:
            raise HTTPException(status_code=500, detail="Cloudflare not configured on platform")

        async with httpx.AsyncClient() as http:
            # Create tunnel
            resp = await http.post(
                f"{CF_API_BASE}/accounts/{CF_ACCOUNT_ID}/cfd_tunnel",
                headers={
                    "Authorization": f"Bearer {CF_API_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "name": f"mybeacon-{subdomain}",
                    "config_src": "cloudflare",
                },
            )

            if resp.status_code != 200 or not resp.json().get("success"):
                raise HTTPException(status_code=500, detail=f"Failed to create tunnel: {resp.text[:200]}")

            tunnel_data = resp.json()["result"]
            tunnel_id = tunnel_data["id"]
            tunnel_token = tunnel_data["token"]

            # Create CNAME DNS record (deletes existing first)
            await create_cname_record(http, subdomain, tunnel_id)
            
            # Disable Cloudflare optimizations that break HA frontend
            await disable_cloudflare_optimizations(http)

        client.cloudflare_tunnel_id = tunnel_id
        client.cloudflare_tunnel_token = tunnel_token
        await db.flush()
        await db.refresh(client)

        # Mark token as used
        token_obj.last_used = datetime.now()
        await db.flush()

    if not client.cloudflare_tunnel_id:
        raise HTTPException(status_code=500, detail="Tunnel not available")

    # Return both naming conventions for backward compatibility with current agent code
    return {
        tunnel_id: client.cloudflare_tunnel_id,
        tunnel_token: client.cloudflare_tunnel_token,
        hostname: hostname,
        account_tag: CF_ACCOUNT_ID,
        id: client.cloudflare_tunnel_id,
        token: client.cloudflare_tunnel_token,
    }


@router.get("/{client_id}", response_model=TunnelInfo)
async def get_tunnel(client_id: int, db: AsyncSession = Depends(get_db)):
    """Get tunnel info for a client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    hostname = f"{client.subdomain}.{CF_DOMAIN}"

    if client.cloudflare_tunnel_id:
        return TunnelInfo(
            tunnel_id=client.cloudflare_tunnel_id,
            tunnel_token=client.cloudflare_tunnel_token,
            hostname=hostname,
            status="active",
            remote_access_url=f"https://{hostname}",
        )
    else:
        return TunnelInfo(
            tunnel_id=None,
            tunnel_token=None,
            hostname=hostname,
            status="not_created",
            remote_access_url=None,
        )


@router.get("/", response_model=List[TunnelInfo])
async def list_tunnels(db: AsyncSession = Depends(get_db)):
    """List all clients with tunnel info."""
    result = await db.execute(select(Client).where(Client.cloudflare_tunnel_id.isnot(None)))
    clients = result.scalars().all()
    tunnels = []
    for client in clients:
        hostname = f"{client.subdomain}.{CF_DOMAIN}"
        tunnels.append(TunnelInfo(
            tunnel_id=client.cloudflare_tunnel_id,
            tunnel_token=client.cloudflare_tunnel_token,
            hostname=hostname,
            status="active",
            remote_access_url=f"https://{hostname}",
        ))
    return tunnels


@router.delete("/{client_id}")
async def delete_tunnel(client_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a Cloudflare tunnel for a client."""
    if not CF_API_TOKEN or not CF_ACCOUNT_ID:
        raise HTTPException(status_code=500, detail="Cloudflare API not configured")

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.cloudflare_tunnel_id:
        raise HTTPException(status_code=400, detail="No tunnel exists for this client")

    async with httpx.AsyncClient() as http:
        # Delete tunnel from Cloudflare
        await http.delete(
            f"{CF_API_BASE}/accounts/{CF_ACCOUNT_ID}/cfd_tunnel/{client.cloudflare_tunnel_id}",
            headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
        )

        # Delete DNS records
        await delete_existing_cname(http, client.subdomain)

    client.cloudflare_tunnel_id = None
    client.cloudflare_tunnel_token = None
    await db.flush()

    return {"status": "deleted", "client_id": client_id}


@router.post("/{client_id}/disable")
async def disable_tunnel(client_id: int, db: AsyncSession = Depends(get_db)):
    """Disable a tunnel by removing the CNAME record."""
    if not CF_API_TOKEN or not CF_ZONE_ID:
        raise HTTPException(status_code=500, detail="Cloudflare not configured")

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.cloudflare_tunnel_id:
        raise HTTPException(status_code=400, detail="No tunnel exists for this client")

    async with httpx.AsyncClient() as http:
        await delete_existing_cname(http, client.subdomain)

    return {"status": "disabled", "client_id": client_id}
