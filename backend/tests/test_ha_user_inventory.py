import asyncio
from datetime import datetime, timedelta
import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from admin_auth import get_current_admin
from database import Base, get_db
from models import (
    Client, ClientStatus, HAUserInventory, HAUserInventoryRequest,
    SecurityAuditEvent, SubscriptionToken,
)
from routers import ha_users


class HAUserInventoryPlatformTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        asyncio.run(self._create_schema())
        self.app = FastAPI()
        self.app.include_router(ha_users.router, prefix="/api/ha-users")

        async def test_db():
            async with self.sessions() as db:
                try:
                    yield db
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise

        self.app.dependency_overrides[get_db] = test_db
        self.app.dependency_overrides[get_current_admin] = lambda: {
            "username": "inventory-admin", "role": "admin",
        }
        self.http = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.http.close()
        asyncio.run(self.engine.dispose())

    async def _create_schema(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def _client(self, suffix):
        async with self.sessions() as db:
            client = Client(
                name=f"Client {suffix}",
                email=f"{suffix}@example.test",
                subdomain=f"inventory-{suffix}",
                status=ClientStatus.ACTIVE,
            )
            db.add(client)
            await db.flush()
            token = SubscriptionToken(
                client_id=client.id,
                token=f"inventory-token-{suffix}",
                is_active=True,
            )
            db.add(token)
            await db.commit()
            return client.id, token.token

    @staticmethod
    def _headers(token):
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _users():
        return [{
            "id": "owner-id", "name": "Owner", "username": "owner",
            "is_owner": True, "is_admin": True, "is_active": True,
            "local_only": False, "system_generated": False,
            "credential_providers": ["homeassistant"],
        }, {
            "id": "external-id", "name": "External", "username": None,
            "is_owner": False, "is_admin": False, "is_active": False,
            "local_only": True, "system_generated": True,
            "credential_providers": ["trusted_networks"],
        }]

    def _enable_and_refresh(self, client_id, token):
        capability = self.http.post(
            "/api/ha-users/agent/capabilities",
            headers=self._headers(token),
            json={"ha_users_read": True},
        )
        self.assertEqual(capability.status_code, 200, capability.text)
        refresh = self.http.post(f"/api/ha-users/clients/{client_id}/refresh")
        self.assertEqual(refresh.status_code, 202, refresh.text)
        return refresh.json()["request_id"]

    def test_authenticated_capability_refresh_claim_result_and_cached_read(self):
        client_id, token = asyncio.run(self._client("success"))
        request_id = self._enable_and_refresh(client_id, token)
        claim = self.http.get(
            "/api/ha-users/agent/requests/next",
            headers=self._headers(token),
        )
        self.assertEqual(claim.status_code, 200, claim.text)
        self.assertEqual(claim.json()["request_id"], request_id)
        result = self.http.post(
            f"/api/ha-users/agent/requests/{request_id}/result",
            headers=self._headers(token),
            json={"status": "completed", "users": self._users()},
        )
        self.assertEqual(result.status_code, 200, result.text)
        represented = self.http.get(f"/api/ha-users/clients/{client_id}")
        self.assertEqual(represented.status_code, 200, represented.text)
        body = represented.json()
        self.assertTrue(body["ha_users_read"])
        self.assertEqual(len(body["users"]), 2)
        self.assertIsNone(body["users"][1]["username"])
        self.assertIsNotNone(body["refreshed_at"])
        self.assertIsNone(body["last_error_code"])

        async def audit_count():
            async with self.sessions() as db:
                return len((await db.execute(select(SecurityAuditEvent))).scalars().all())
        self.assertEqual(asyncio.run(audit_count()), 1)

    def test_agent_authentication_and_cross_client_isolation(self):
        first_id, first_token = asyncio.run(self._client("first"))
        second_id, second_token = asyncio.run(self._client("second"))
        request_id = self._enable_and_refresh(first_id, first_token)
        self.assertEqual(
            self.http.get("/api/ha-users/agent/requests/next").status_code, 401
        )
        self.assertEqual(
            self.http.get(
                "/api/ha-users/agent/requests/next",
                headers=self._headers(second_token),
            ).status_code,
            204,
        )
        self.assertEqual(
            self.http.get(
                "/api/ha-users/agent/requests/next",
                headers=self._headers(first_token),
            ).status_code,
            200,
        )
        wrong = self.http.post(
            f"/api/ha-users/agent/requests/{request_id}/result",
            headers=self._headers(second_token),
            json={"status": "completed", "users": []},
        )
        self.assertEqual(wrong.status_code, 404)
        self.assertEqual(self.http.get("/api/ha-users/clients/999999").status_code, 404)

    def test_management_inventory_requires_authentication(self):
        client_id, _ = asyncio.run(self._client("admin-auth"))
        override = self.app.dependency_overrides.pop(get_current_admin)
        try:
            self.assertEqual(
                self.http.get(f"/api/ha-users/clients/{client_id}").status_code,
                401,
            )
        finally:
            self.app.dependency_overrides[get_current_admin] = override

    def test_older_agent_and_explicit_unsupported_capability(self):
        client_id, token = asyncio.run(self._client("legacy"))
        legacy = self.http.get(f"/api/ha-users/clients/{client_id}")
        self.assertEqual(legacy.status_code, 200)
        self.assertFalse(legacy.json()["ha_users_read"])
        self.assertIsNone(legacy.json()["capability_reported_at"])
        self.assertEqual(
            self.http.post(f"/api/ha-users/clients/{client_id}/refresh").status_code,
            409,
        )
        unsupported = self.http.post(
            "/api/ha-users/agent/capabilities",
            headers=self._headers(token),
            json={"ha_users_read": False},
        )
        self.assertEqual(unsupported.status_code, 200)
        state = self.http.get(f"/api/ha-users/clients/{client_id}").json()
        self.assertEqual(state["last_error_code"], "unsupported")

    def test_permission_error_and_malformed_or_secret_payload_rejection(self):
        client_id, token = asyncio.run(self._client("errors"))
        request_id = self._enable_and_refresh(client_id, token)
        self.http.get(
            "/api/ha-users/agent/requests/next",
            headers=self._headers(token),
        )
        failed = self.http.post(
            f"/api/ha-users/agent/requests/{request_id}/result",
            headers=self._headers(token),
            json={"status": "failed", "error_code": "permission_required"},
        )
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(
            self.http.get(f"/api/ha-users/clients/{client_id}").json()["last_error_code"],
            "permission_required",
        )

        second = self.http.post(f"/api/ha-users/clients/{client_id}/refresh").json()["request_id"]
        self.http.get("/api/ha-users/agent/requests/next", headers=self._headers(token))
        secret = self._users()[0] | {"password": "must-not-pass"}
        rejected = self.http.post(
            f"/api/ha-users/agent/requests/{second}/result",
            headers=self._headers(token),
            json={"status": "completed", "users": [secret]},
        )
        self.assertEqual(rejected.status_code, 422)

    def test_refresh_timeout_preserves_last_good_data(self):
        client_id, token = asyncio.run(self._client("stale"))
        request_id = self._enable_and_refresh(client_id, token)
        self.http.get("/api/ha-users/agent/requests/next", headers=self._headers(token))
        self.http.post(
            f"/api/ha-users/agent/requests/{request_id}/result",
            headers=self._headers(token),
            json={"status": "completed", "users": self._users()},
        )
        stale_request = self.http.post(
            f"/api/ha-users/clients/{client_id}/refresh"
        ).json()["request_id"]

        async def expire():
            async with self.sessions() as db:
                request = (
                    await db.execute(
                        select(HAUserInventoryRequest).where(
                            HAUserInventoryRequest.request_id == stale_request
                        )
                    )
                ).scalars().one()
                request.expires_at = datetime.utcnow() - timedelta(seconds=1)
                await db.commit()
        asyncio.run(expire())
        state = self.http.get(f"/api/ha-users/clients/{client_id}").json()
        self.assertEqual(state["request"]["state"], "failed")
        self.assertEqual(state["last_error_code"], "timeout")
        self.assertEqual(len(state["users"]), 2)
        self.assertIsNotNone(state["refreshed_at"])


if __name__ == "__main__":
    unittest.main()
