import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from database import Base, get_db
from models import Client, ClientStatus, HomeAssistantInstance, SubscriptionToken
from routers import agent, instances


class AgentFirstHeartbeatTests(unittest.TestCase):
    def setUp(self):
        agent.agent_reports.clear()
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        asyncio.run(self._create_schema())
        self.app = FastAPI()
        self.app.include_router(agent.router, prefix="/api/agent")
        self.app.include_router(instances.router, prefix="/api/instances")

        async def test_db():
            async with self.sessions() as db:
                try:
                    yield db
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise

        self.app.dependency_overrides[get_db] = test_db
        self.http = TestClient(self.app, raise_server_exceptions=False)

    def tearDown(self):
        self.http.close()
        asyncio.run(self.engine.dispose())
        agent.agent_reports.clear()

    async def _create_schema(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def _client_and_token(self, suffix):
        async with self.sessions() as db:
            client = Client(name=f"Generated {suffix}", email=f"{suffix}@example.test", subdomain=f"generated-{suffix}", status=ClientStatus.ACTIVE)
            db.add(client)
            await db.flush()
            token = SubscriptionToken(client_id=client.id, token=f"token-{suffix}", is_active=True)
            db.add(token)
            await db.commit()
            return client.id, token.token

    async def _instances_for(self, client_id):
        async with self.sessions() as db:
            return (await db.execute(select(HomeAssistantInstance).where(HomeAssistantInstance.client_id == client_id).order_by(HomeAssistantInstance.id))).scalars().all()

    @staticmethod
    def _report(**overrides):
        report = {"ha_version": "2026.7.4", "entities_count": 200, "automations_count": 12, "updates_available": [], "disk_usage_percent": 41.5, "disk_total_gb": 64, "disk_used_gb": 26.5, "cpu_usage_percent": 9.0, "memory_usage_percent": 32.0, "memory_total_gb": 8, "memory_used_gb": 2.5, "uptime_seconds": 12345, "ip_address": "192.0.2.10", "hostname": "generated-ha", "integrations": ["cloud"], "addons": [{"slug": "burghscape_agent", "version": "0.2.55"}], "tunnel_running": True, "onboarding_status": "ready"}
        report.update(overrides)
        return report

    def _heartbeat(self, token, report=None):
        return self.http.post("/api/agent/report", headers={"Authorization": f"Bearer {token}"}, json=report or self._report())

    def test_first_heartbeat_creates_one_online_instance_and_second_updates_it(self):
        client_id, token = asyncio.run(self._client_and_token("first"))
        self.assertEqual(asyncio.run(self._instances_for(client_id)), [])
        first = self._heartbeat(token)
        self.assertEqual(first.status_code, 200, first.text)
        created = asyncio.run(self._instances_for(client_id))
        self.assertEqual(len(created), 1)
        instance_id = created[0].id
        self.assertTrue(created[0].is_online)
        self.assertEqual(created[0].entities_count, 200)
        self.assertEqual(created[0].ha_version, "2026.7.4")
        self.assertIsNotNone(created[0].last_seen)
        self.assertTrue(agent.agent_reports["generated-first"]["tunnel_running"])
        second = self._heartbeat(token, self._report(entities_count=201))
        self.assertEqual(second.status_code, 200, second.text)
        updated = asyncio.run(self._instances_for(client_id))
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].id, instance_id)
        self.assertEqual(updated[0].entities_count, 201)
        represented = self.http.get("/api/instances")
        self.assertEqual(represented.status_code, 200, represented.text)
        item = next(row for row in represented.json() if row["client_id"] == client_id)
        self.assertTrue(item["is_online"])

    def test_existing_offline_instance_returns_online_without_duplication(self):
        client_id, token = asyncio.run(self._client_and_token("offline"))
        async def seed():
            async with self.sessions() as db:
                db.add(HomeAssistantInstance(client_id=client_id, name="Existing", is_online=False))
                await db.commit()
        asyncio.run(seed())
        with patch.object(agent, "send_email"):
            response = self._heartbeat(token)
        self.assertEqual(response.status_code, 200, response.text)
        records = asyncio.run(self._instances_for(client_id))
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].is_online)

    def test_token_isolation_and_invalid_token(self):
        first_id, first_token = asyncio.run(self._client_and_token("alpha"))
        second_id, second_token = asyncio.run(self._client_and_token("beta"))
        self.assertEqual(self._heartbeat(first_token).status_code, 200)
        self.assertEqual(self._heartbeat(second_token, self._report(entities_count=77)).status_code, 200)
        self.assertEqual(self._heartbeat("invalid-token").status_code, 401)
        first = asyncio.run(self._instances_for(first_id)); second = asyncio.run(self._instances_for(second_id))
        self.assertEqual((len(first), len(second)), (1, 1))
        self.assertEqual((first[0].entities_count, second[0].entities_count), (200, 77))

    def test_backup_timestamp_valid_absent_and_malformed(self):
        client_id, token = asyncio.run(self._client_and_token("backup"))
        valid = self._heartbeat(token, self._report(backup_status={"enabled": True, "interval_hours": 24, "last_backup": 1_700_000_000}))
        self.assertEqual(valid.status_code, 200, valid.text)
        valid_value = asyncio.run(self._instances_for(client_id))[0].last_backup
        self.assertIsNotNone(valid_value)
        self.assertEqual(self._heartbeat(token, self._report(backup_status={"enabled": True})).status_code, 200)
        self.assertEqual(asyncio.run(self._instances_for(client_id))[0].last_backup, valid_value)
        malformed = self._heartbeat(token, self._report(backup_status={"enabled": True, "last_backup": "not-a-timestamp"}))
        self.assertEqual(malformed.status_code, 200, malformed.text)
        self.assertEqual(asyncio.run(self._instances_for(client_id))[0].last_backup, valid_value)

    def test_failed_transaction_rolls_back_new_instance_and_retry_is_safe(self):
        client_id, token = asyncio.run(self._client_and_token("rollback"))
        fail_commit = {"enabled": True}
        async def failing_db():
            async with self.sessions() as db:
                original_flush = db.flush
                async def controlled_flush(*args, **kwargs):
                    if fail_commit["enabled"]:
                        raise RuntimeError("simulated database failure")
                    return await original_flush(*args, **kwargs)
                db.flush = controlled_flush
                try:
                    yield db
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
        self.app.dependency_overrides[get_db] = failing_db
        failed = self._heartbeat(token)
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(asyncio.run(self._instances_for(client_id)), [])
        fail_commit["enabled"] = False
        retry = self._heartbeat(token)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(len(asyncio.run(self._instances_for(client_id))), 1)


if __name__ == "__main__":
    unittest.main()
