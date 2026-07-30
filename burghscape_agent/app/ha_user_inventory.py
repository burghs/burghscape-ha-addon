"""Read-only Home Assistant user inventory over the supported WebSocket API."""
import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp


class HAUserInventoryError(Exception):
    """A sanitized inventory error safe to report to the Platform."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class HAUserInventoryResult:
    users: list[dict[str, Any]]


def _websocket_url(ha_url: str) -> str:
    parsed = urlsplit(ha_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, f"{parsed.path}/api/websocket", "", ""))


def _expect_message(message: aiohttp.WSMessage) -> dict[str, Any]:
    if message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING):
        raise HAUserInventoryError("unavailable")
    if message.type == aiohttp.WSMsgType.ERROR:
        raise HAUserInventoryError("unavailable")
    if message.type != aiohttp.WSMsgType.TEXT:
        raise HAUserInventoryError("malformed_response")
    try:
        payload = message.json()
    except (TypeError, ValueError):
        raise HAUserInventoryError("malformed_response") from None
    if not isinstance(payload, dict):
        raise HAUserInventoryError("malformed_response")
    return payload


def _normalize_user(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise HAUserInventoryError("malformed_response")
    required = {
        "id": str, "is_owner": bool, "is_active": bool, "local_only": bool,
        "system_generated": bool, "group_ids": list, "credentials": list,
    }
    if any(key not in raw or not isinstance(raw[key], value_type) for key, value_type in required.items()):
        raise HAUserInventoryError("malformed_response")
    if raw.get("name") is not None and not isinstance(raw.get("name"), str):
        raise HAUserInventoryError("malformed_response")
    if raw.get("username") is not None and not isinstance(raw.get("username"), str):
        raise HAUserInventoryError("malformed_response")
    if any(not isinstance(group_id, str) for group_id in raw["group_ids"]):
        raise HAUserInventoryError("malformed_response")
    providers: list[str] = []
    for credential in raw["credentials"]:
        if not isinstance(credential, dict) or not isinstance(credential.get("type"), str):
            raise HAUserInventoryError("malformed_response")
        if credential["type"] not in providers:
            providers.append(credential["type"])
    is_owner = raw["is_owner"]
    return {
        "id": raw["id"], "name": raw.get("name"), "username": raw.get("username"),
        "is_owner": is_owner,
        "is_admin": bool(is_owner or (raw["is_active"] and "system-admin" in raw["group_ids"])),
        "is_active": raw["is_active"], "local_only": raw["local_only"],
        "system_generated": raw["system_generated"], "credential_providers": providers,
    }


class HAUserInventoryClient:
    """Fetch a strictly validated read-only user list from Home Assistant."""

    def __init__(self, ha_url: str, ha_token: str, timeout_seconds: float = 10):
        self.websocket_url = _websocket_url(ha_url)
        self.ha_token = ha_token
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def fetch(self) -> HAUserInventoryResult:
        if not self.ha_token:
            raise HAUserInventoryError("authentication_required")
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.ws_connect(self.websocket_url, autoping=True) as websocket:
                    greeting = _expect_message(await websocket.receive())
                    if greeting.get("type") != "auth_required":
                        raise HAUserInventoryError("malformed_response")
                    await websocket.send_json({"type": "auth", "access_token": self.ha_token})
                    auth = _expect_message(await websocket.receive())
                    if auth.get("type") == "auth_invalid":
                        raise HAUserInventoryError("authentication_failed")
                    if auth.get("type") != "auth_ok":
                        raise HAUserInventoryError("malformed_response")
                    await websocket.send_json({"id": 1, "type": "config/auth/list"})
                    response = _expect_message(await websocket.receive())
                    if response.get("id") != 1 or response.get("type") != "result" or not isinstance(response.get("success"), bool):
                        raise HAUserInventoryError("malformed_response")
                    if not response["success"]:
                        error = response.get("error")
                        code = error.get("code") if isinstance(error, dict) else None
                        if code in {"unauthorized", "not_admin", "permission_denied"}:
                            raise HAUserInventoryError("permission_required")
                        if code in {"unknown_command", "not_found"}:
                            raise HAUserInventoryError("unsupported")
                        raise HAUserInventoryError("unavailable")
                    users = response.get("result")
                    if not isinstance(users, list) or len(users) > 1000:
                        raise HAUserInventoryError("malformed_response")
                    return HAUserInventoryResult([_normalize_user(user) for user in users])
        except HAUserInventoryError:
            raise
        except (asyncio.TimeoutError, TimeoutError):
            raise HAUserInventoryError("timeout") from None
        except (aiohttp.ClientError, OSError):
            raise HAUserInventoryError("unavailable") from None
