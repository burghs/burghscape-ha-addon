import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiohttp import WSMsgType

ROOT = Path(__file__).resolve().parents[1] / "burghscape_agent"
sys.path.insert(0, str(ROOT))

from app.ha_user_inventory import HAUserInventoryClient, HAUserInventoryError


class Message:
    type = WSMsgType.TEXT

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class WebSocket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []

    async def receive(self):
        return next(self.messages)

    async def send_json(self, payload):
        self.sent.append(payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


class Session:
    def __init__(self, websocket):
        self.websocket = websocket

    def ws_connect(self, *_args, **_kwargs):
        return self.websocket

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None


def user(**overrides):
    value = {
        "id": "u1", "name": "Owner", "username": "owner",
        "is_owner": True, "is_active": True, "local_only": False,
        "system_generated": False, "group_ids": ["system-users"],
        "credentials": [{"type": "homeassistant"}],
    }
    value.update(overrides)
    return value


class HAUserInventoryTests(unittest.TestCase):
    def run_fetch(self, result, auth=None):
        websocket = WebSocket([
            Message({"type": "auth_required"}),
            Message(auth or {"type": "auth_ok"}),
            Message(result),
        ])
        with patch("app.ha_user_inventory.aiohttp.ClientSession", return_value=Session(websocket)):
            fetched = asyncio.run(HAUserInventoryClient("http://localhost:8123", "secret").fetch())
        return fetched, websocket

    def test_authenticates_and_lists_local_external_inactive_and_system_users(self):
        result = {"id": 1, "type": "result", "success": True, "result": [
            user(),
            user(id="u2", name="Admin", username=None, is_owner=False,
                 group_ids=["system-admin"], credentials=[{"type": "trusted_networks"}]),
            user(id="u3", name=None, username=None, is_owner=False, is_active=False,
                 system_generated=True, group_ids=["system-admin"], credentials=[]),
        ]}
        inventory, websocket = self.run_fetch(result)
        self.assertEqual(websocket.sent[0], {"type": "auth", "access_token": "secret"})
        self.assertEqual(websocket.sent[1], {"id": 1, "type": "config/auth/list"})
        self.assertTrue(inventory.users[0]["is_admin"])
        self.assertIsNone(inventory.users[1]["username"])
        self.assertTrue(inventory.users[1]["is_admin"])
        self.assertFalse(inventory.users[2]["is_admin"])
        self.assertTrue(inventory.users[2]["system_generated"])

    def test_permission_denied_and_unsupported_are_sanitized(self):
        for code, expected in [
            ("unauthorized", "permission_required"),
            ("unknown_command", "unsupported"),
        ]:
            with self.subTest(code=code):
                with self.assertRaises(HAUserInventoryError) as caught:
                    self.run_fetch({"id": 1, "type": "result", "success": False,
                                    "error": {"code": code, "message": "secret detail"}})
                self.assertEqual(caught.exception.code, expected)

    def test_authentication_failure(self):
        with self.assertRaises(HAUserInventoryError) as caught:
            self.run_fetch({}, auth={"type": "auth_invalid", "message": "token detail"})
        self.assertEqual(caught.exception.code, "authentication_failed")

    def test_malformed_response_is_rejected(self):
        for malformed in [
            None, {}, [{"id": "missing fields"}],
            [user(credentials=[{"unexpected": "value"}])],
        ]:
            with self.subTest(malformed=malformed):
                with self.assertRaises(HAUserInventoryError) as caught:
                    self.run_fetch({"id": 1, "type": "result", "success": True,
                                    "result": malformed})
                self.assertEqual(caught.exception.code, "malformed_response")

    def test_timeout_is_sanitized(self):
        session = AsyncMock()
        session.__aenter__.side_effect = asyncio.TimeoutError
        with patch("app.ha_user_inventory.aiohttp.ClientSession", return_value=session):
            with self.assertRaises(HAUserInventoryError) as caught:
                asyncio.run(HAUserInventoryClient("http://localhost:8123", "secret").fetch())
        self.assertEqual(caught.exception.code, "timeout")

    def test_source_does_not_log_tokens_or_user_payloads(self):
        source = (ROOT / "app" / "ha_user_inventory.py").read_text()
        self.assertNotIn("logger.", source)
        self.assertNotIn("print(", source)

    def test_worker_is_separate_from_heartbeat_loop(self):
        source = (ROOT / "app" / "main.py").read_text()
        self.assertIn("asyncio.create_task(ha_user_inventory_loop())", source)
        run_once = source[source.index("async def run_once"):source.index("def utc_timestamp")]
        self.assertNotIn("ha_user_inventory", run_once)


if __name__ == "__main__":
    unittest.main()
