"""Isolated read-only Home Assistant user inventory command and cache API."""
from datetime import datetime, timedelta
import secrets
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_auth import get_current_admin
from database import get_db
from models import Client, HAUserInventory, HAUserInventoryRequest, SecurityAuditEvent
from routers.agent import validate_token


router = APIRouter()
REQUEST_TIMEOUT = timedelta(seconds=45)
ACTIVE_STATES = {"pending", "claimed"}
ERROR_CODES = {
    "authentication_required", "authentication_failed", "permission_required",
    "unsupported", "malformed_response", "timeout", "unavailable",
}


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ha_users_read: bool


class InventoryUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=255)
    name: Optional[str] = Field(default=None, max_length=255)
    username: Optional[str] = Field(default=None, max_length=255)
    is_owner: bool
    is_admin: bool
    is_active: bool
    local_only: bool
    system_generated: bool
    credential_providers: list[str] = Field(max_length=20)


class InventoryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "failed"]
    users: Optional[list[InventoryUser]] = Field(default=None, max_length=1000)
    error_code: Optional[str] = Field(default=None, max_length=50)


async def _inventory(db: AsyncSession, client_id: int) -> HAUserInventory:
    row = (
        await db.execute(
            select(HAUserInventory).where(HAUserInventory.client_id == client_id)
        )
    ).scalars().first()
    if row is None:
        row = HAUserInventory(client_id=client_id, ha_users_read=False, users=[])
        db.add(row)
        await db.flush()
    return row


def _request_dict(request: HAUserInventoryRequest) -> dict:
    return {
        "request_id": request.request_id,
        "state": request.state,
        "error_code": request.error_code,
        "created_at": request.created_at.isoformat() if request.created_at else None,
        "claimed_at": request.claimed_at.isoformat() if request.claimed_at else None,
        "completed_at": request.completed_at.isoformat() if request.completed_at else None,
        "expires_at": request.expires_at.isoformat() if request.expires_at else None,
    }


async def _expire_request(
    request: HAUserInventoryRequest,
    inventory: HAUserInventory,
    now: datetime,
) -> None:
    if request.state in ACTIVE_STATES and request.expires_at <= now:
        request.state = "failed"
        request.error_code = "timeout"
        request.completed_at = now
        inventory.last_error_code = "timeout"


@router.post("/agent/capabilities")
async def report_capabilities(
    report: CapabilityReport,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Missing bearer token")
    client, _ = await validate_token(token, db)
    inventory = await _inventory(db, client.id)
    inventory.ha_users_read = report.ha_users_read
    inventory.capability_reported_at = datetime.utcnow()
    if not report.ha_users_read:
        inventory.last_error_code = "unsupported"
    await db.flush()
    return {"ha_users_read": inventory.ha_users_read}


@router.get("/agent/requests/next")
async def claim_request(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Missing bearer token")
    client, _ = await validate_token(token, db)
    inventory = await _inventory(db, client.id)
    now = datetime.utcnow()
    requests = (
        await db.execute(
            select(HAUserInventoryRequest)
            .where(
                HAUserInventoryRequest.client_id == client.id,
                HAUserInventoryRequest.state.in_(ACTIVE_STATES),
            )
            .order_by(HAUserInventoryRequest.created_at)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    for request in requests:
        await _expire_request(request, inventory, now)
        if request.state == "pending":
            request.state = "claimed"
            request.claimed_at = now
            await db.flush()
            return {
                "request_id": request.request_id,
                "expires_at": request.expires_at.isoformat(),
            }
    await db.flush()
    return Response(status_code=204)


@router.post("/agent/requests/{request_id}/result")
async def report_result(
    request_id: str,
    result: InventoryResult,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Missing bearer token")
    client, _ = await validate_token(token, db)
    request = (
        await db.execute(
            select(HAUserInventoryRequest)
            .where(HAUserInventoryRequest.request_id == request_id)
            .with_for_update()
        )
    ).scalars().first()
    if request is None or request.client_id != client.id:
        raise HTTPException(404, "Inventory request not found")
    if request.state != "claimed":
        raise HTTPException(409, "Inventory request is not active")
    now = datetime.utcnow()
    inventory = await _inventory(db, client.id)
    if request.expires_at <= now:
        await _expire_request(request, inventory, now)
        raise HTTPException(409, "Inventory request expired")
    if result.status == "completed":
        if result.users is None or result.error_code is not None:
            raise HTTPException(400, "Completed inventory requires users only")
        inventory.users = [user.model_dump() for user in result.users]
        inventory.refreshed_at = now
        inventory.last_error_code = None
        request.state = "completed"
        request.error_code = None
    else:
        if result.users is not None or result.error_code not in ERROR_CODES:
            raise HTTPException(400, "Failed inventory requires a supported error code only")
        inventory.last_error_code = result.error_code
        request.state = "failed"
        request.error_code = result.error_code
    request.completed_at = now
    await db.flush()
    return _request_dict(request)


@router.get("/clients/{client_id}")
async def get_inventory(
    client_id: int,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    client = (
        await db.execute(select(Client).where(Client.id == client_id))
    ).scalars().first()
    if client is None:
        raise HTTPException(404, "Client not found")
    inventory = await _inventory(db, client.id)
    latest = (
        await db.execute(
            select(HAUserInventoryRequest)
            .where(HAUserInventoryRequest.client_id == client.id)
            .order_by(desc(HAUserInventoryRequest.created_at))
        )
    ).scalars().first()
    if latest:
        await _expire_request(latest, inventory, datetime.utcnow())
    await db.flush()
    return {
        "client_id": client.id,
        "client_name": client.name,
        "ha_users_read": bool(inventory.ha_users_read),
        "capability_reported_at": (
            inventory.capability_reported_at.isoformat()
            if inventory.capability_reported_at else None
        ),
        "users": inventory.users or [],
        "refreshed_at": inventory.refreshed_at.isoformat() if inventory.refreshed_at else None,
        "last_error_code": inventory.last_error_code,
        "request": _request_dict(latest) if latest else None,
    }


@router.post("/clients/{client_id}/refresh", status_code=202)
async def refresh_inventory(
    client_id: int,
    request: Request,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    client = (
        await db.execute(
            select(Client).where(Client.id == client_id).with_for_update()
        )
    ).scalars().first()
    if client is None:
        raise HTTPException(404, "Client not found")
    inventory = await _inventory(db, client.id)
    if not inventory.ha_users_read:
        raise HTTPException(409, "HA user inventory is not supported by this Agent")
    now = datetime.utcnow()
    active = (
        await db.execute(
            select(HAUserInventoryRequest)
            .where(
                HAUserInventoryRequest.client_id == client.id,
                HAUserInventoryRequest.state.in_(ACTIVE_STATES),
            )
            .order_by(desc(HAUserInventoryRequest.created_at))
            .with_for_update()
        )
    ).scalars().first()
    if active:
        await _expire_request(active, inventory, now)
    if active and active.state in ACTIVE_STATES:
        return _request_dict(active)
    pending = HAUserInventoryRequest(
        client_id=client.id,
        request_id=secrets.token_hex(16),
        state="pending",
        created_at=now,
        expires_at=now + REQUEST_TIMEOUT,
    )
    db.add(pending)
    db.add(SecurityAuditEvent(
        administrator=admin.get("username"),
        client_id=client.id,
        action="ha_users_inventory_requested",
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:500],
    ))
    await db.flush()
    return _request_dict(pending)
