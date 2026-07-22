import asyncio
import sys
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database import Base
from models import Campaign, CampaignTarget, Client, ClientStatus
from routers import campaigns


class RC141CampaignLifecycleTests(unittest.TestCase):
    def test_admin_create_publish_unpublish_archive_and_draft_delete(self):
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as db:
                client = Client(name="Target", email="target@example.test", subdomain="target", status=ClientStatus.ACTIVE)
                db.add(client); await db.commit(); await db.refresh(client)
                data = campaigns.CampaignInput(
                    internal_name="selected-release", title="Selected release",
                    campaign_type="new_service", body_content="Plain text content",
                    target_all_clients=False, target_client_ids=[client.id], priority=10,
                )
                created = await campaigns.create_campaign(data, {"username": "admin"}, db)
                self.assertEqual(created["status"], "draft")
                self.assertEqual(created["target_client_ids"], [client.id])
                published = await campaigns.publish(created["id"], {"username": "admin"}, db)
                self.assertEqual(published["status"], "published")
                self.assertIsNotNone(published["published_at"])
                with self.assertRaises(HTTPException) as rejected:
                    await campaigns.delete_draft(created["id"], {"username": "admin"}, db)
                self.assertEqual(rejected.exception.status_code, 409)
                unpublished = await campaigns.unpublish(created["id"], {"username": "admin"}, db)
                self.assertEqual(unpublished["status"], "draft")
                archived = await campaigns.archive(created["id"], {"username": "admin"}, db)
                self.assertEqual(archived["status"], "archived")
                targets = (await db.execute(select(CampaignTarget).where(CampaignTarget.campaign_id == created["id"]))).scalars().all()
                self.assertEqual(len(targets), 1)

                draft = await campaigns.create_campaign(
                    campaigns.CampaignInput(internal_name="delete-me", title="Delete me", campaign_type="tip", body_content="Body"),
                    {"username": "admin"}, db,
                )
                result = await campaigns.delete_draft(draft["id"], {"username": "admin"}, db)
                self.assertEqual(result, {"status": "deleted"})
                self.assertIsNone((await db.execute(select(Campaign).where(Campaign.id == draft["id"]))).scalars().first())
            await engine.dispose()
        asyncio.run(scenario())

    def test_immediate_scheduled_no_end_and_expired_publication(self):
        async def scenario():
            engine=create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
            sessions=async_sessionmaker(engine,expire_on_commit=False)
            async with sessions() as db:
                client=Client(name="Schedule",email="schedule@example.test",subdomain="schedule",status=ClientStatus.ACTIVE);db.add(client);await db.commit();await db.refresh(client)
                before=campaigns.now_utc()
                immediate=await campaigns.create_campaign(campaigns.CampaignInput(internal_name="immediate",title="Immediate",campaign_type="announcement",body_content="Body",starts_at=None,ends_at=None),{"username":"admin"},db)
                immediate=await campaigns.publish(immediate["id"],{"username":"admin"},db);after=campaigns.now_utc()
                self.assertIsNone(immediate["starts_at"]);self.assertIsNone(immediate["ends_at"]);self.assertEqual(immediate["delivery_status"],"live")
                published_at=campaigns.datetime.fromisoformat(immediate["published_at"]);self.assertLessEqual(before,published_at);self.assertLessEqual(published_at,after)
                visible=(await db.execute(select(Campaign).where(Campaign.id==immediate["id"],campaigns.visible_clause(client.id,campaigns.now_utc())))).scalars().first();self.assertIsNotNone(visible)
                later=campaigns.now_utc()+timedelta(days=1)
                scheduled=await campaigns.create_campaign(campaigns.CampaignInput(internal_name="scheduled",title="Scheduled",campaign_type="announcement",body_content="Body",starts_at=later),{"username":"admin"},db)
                scheduled=await campaigns.publish(scheduled["id"],{"username":"admin"},db);self.assertEqual(scheduled["delivery_status"],"scheduled")
                hidden=(await db.execute(select(Campaign).where(Campaign.id==scheduled["id"],campaigns.visible_clause(client.id,campaigns.now_utc())))).scalars().first();self.assertIsNone(hidden)
                expired=await campaigns.create_campaign(campaigns.CampaignInput(internal_name="expired-publish",title="Expired",campaign_type="announcement",body_content="Body",ends_at=campaigns.now_utc()-timedelta(seconds=1)),{"username":"admin"},db)
                with self.assertRaises(HTTPException) as rejected: await campaigns.publish(expired["id"],{"username":"admin"},db)
                self.assertEqual(rejected.exception.status_code,422);self.assertIn("future",rejected.exception.detail)
            await engine.dispose()
        asyncio.run(scenario())

    def test_invalid_selected_client_is_rejected_without_replacing_targets(self):
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as db:
                client = Client(name="Target", email="target2@example.test", subdomain="target2", status=ClientStatus.ACTIVE)
                db.add(client); await db.commit(); await db.refresh(client)
                client_id = client.id
                created = await campaigns.create_campaign(
                    campaigns.CampaignInput(internal_name="keep-target", title="Keep", campaign_type="announcement", body_content="Body", target_all_clients=False, target_client_ids=[client.id]),
                    {"username": "admin"}, db,
                )
                bad = campaigns.CampaignInput(internal_name="keep-target", title="Keep", campaign_type="announcement", body_content="Body", target_all_clients=False, target_client_ids=[99999])
                with self.assertRaises(HTTPException) as rejected:
                    await campaigns.update_campaign(created["id"], bad, {"username": "admin"}, db)
                self.assertEqual(rejected.exception.status_code, 422)
                await db.rollback()
                targets = (await db.execute(select(CampaignTarget).where(CampaignTarget.campaign_id == created["id"]))).scalars().all()
                self.assertEqual([target.client_id for target in targets], [client_id])
            await engine.dispose()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
