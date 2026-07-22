import asyncio
import sys
import unittest
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from database import Base
from models import Campaign, CampaignPopupEvent, CampaignReadState, CampaignTarget, Client, ClientStatus, ClientUser, ClientOnboardingState
from routers import campaign_popups, campaigns
from routers.portal_state import popup_evaluated_sessions, portal_sessions


def request(token):
    return Request({"type":"http", "method":"GET", "path":"/", "headers":[(b"cookie", f"portal_token={token}".encode())]})


class RC142CampaignPopupTests(unittest.TestCase):
    def legacy_eligibility_priority_audience_dismissal_and_once_per_session(self):
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as db:
                alpha = Client(name="Alpha", email="alpha@popup.test", subdomain="popup-alpha", status=ClientStatus.ACTIVE)
                beta = Client(name="Beta", email="beta@popup.test", subdomain="popup-beta", status=ClientStatus.ACTIVE)
                db.add_all([alpha,beta]); await db.flush()
                user_a = ClientUser(client_id=alpha.id,name="Alpha",email="alpha-user@popup.test",password_hash="x",is_active=True)
                user_b = ClientUser(client_id=beta.id,name="Beta",email="beta-user@popup.test",password_hash="x",is_active=True)
                db.add_all([user_a,user_b]); await db.flush()
                db.add_all([ClientOnboardingState(client_user_id=user_a.id,onboarding_version="rc1.4.3",status="skipped"),ClientOnboardingState(client_user_id=user_b.id,onboarding_version="rc1.4.3",status="skipped")]); await db.flush()
                now=campaigns.now_utc()
                def item(name, **values):
                    defaults=dict(internal_name=name,title=name,campaign_type="promotion",body_content="Body",status="published",published_at=now,created_by="admin",updated_by="admin",target_all_clients=True,popup_enabled=True,priority=1)
                    defaults.update(values); return Campaign(**defaults)
                low=item("low",priority=2,starts_at=now-timedelta(days=3))
                newest=item("newest",priority=9,starts_at=now-timedelta(hours=1))
                older=item("older",priority=9,starts_at=now-timedelta(days=2))
                disabled=item("disabled",priority=99,popup_enabled=False)
                future=item("future",priority=99,starts_at=now+timedelta(days=1))
                expired=item("expired",priority=99,ends_at=now-timedelta(seconds=1))
                inactive=item("inactive",priority=99,status="draft",published_at=None)
                targeted=item("targeted-beta",priority=100,target_all_clients=False)
                db.add_all([low,newest,older,disabled,future,expired,inactive,targeted]); await db.flush()
                db.add(CampaignTarget(campaign_id=targeted.id,client_id=beta.id)); await db.commit()

                token_a="popup-a-1";portal_sessions[token_a]=user_a.id
                selected=await campaign_popups.login_popup(request(token_a),db)
                self.assertEqual(selected["promotion"]["title"],"newest")
                self.assertEqual((await campaign_popups.login_popup(request(token_a),db))["promotion"],None)

                await campaign_popups.dismissed(newest.id,request(token_a),db)
                token_a2="popup-a-2";portal_sessions[token_a2]=user_a.id
                self.assertEqual((await campaign_popups.login_popup(request(token_a2),db))["promotion"]["title"],"older")

                token_b="popup-b-1";portal_sessions[token_b]=user_b.id
                self.assertEqual((await campaign_popups.login_popup(request(token_b),db))["promotion"]["title"],"targeted-beta")
                with self.assertRaises(HTTPException) as denied:
                    await campaign_popups.opened(targeted.id,request(token_a),db)
                self.assertEqual(denied.exception.status_code,404)
                for token in (token_a,token_a2,token_b): portal_sessions.pop(token,None);popup_evaluated_sessions.discard(token)
            await engine.dispose()
        asyncio.run(scenario())

    def legacy_tracking_counts_read_state_completion_and_reset(self):
        async def scenario():
            engine=create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
            sessions=async_sessionmaker(engine,expire_on_commit=False)
            async with sessions() as db:
                client=Client(name="Client",email="track@popup.test",subdomain="popup-track",status=ClientStatus.ACTIVE)
                db.add(client);await db.flush()
                user=ClientUser(client_id=client.id,name="User",email="track-user@popup.test",password_hash="x",is_active=True)
                db.add(user);await db.flush()
                db.add(ClientOnboardingState(client_user_id=user.id,onboarding_version="rc1.4.3",status="skipped"));await db.flush()
                campaign=Campaign(internal_name="tracking",title="Tracking",campaign_type="promotion",body_content="Body",status="published",published_at=campaigns.now_utc(),created_by="admin",updated_by="admin",target_all_clients=True,popup_enabled=True,call_to_action_label="Learn more",call_to_action_url="https://example.com/service")
                db.add(campaign);await db.commit()
                token="popup-track";portal_sessions[token]=user.id;req=request(token)
                await campaign_popups.displayed(campaign.id,req,db)
                await campaign_popups.displayed(campaign.id,req,db)
                self.assertEqual((await db.execute(select(func.count(CampaignReadState.id)))).scalar(),0)
                await campaign_popups.opened(campaign.id,req,db)
                self.assertEqual((await db.execute(select(func.count(CampaignReadState.id)))).scalar(),1)
                await campaign_popups.dismissed(campaign.id,req,db)
                await campaign_popups.dismissed(campaign.id,req,db)
                events=(await db.execute(select(CampaignPopupEvent.event_type).where(CampaignPopupEvent.campaign_id==campaign.id))).scalars().all()
                self.assertEqual(events.count("displayed"),1)
                self.assertEqual(events.count("dismissed"),1)
                self.assertEqual(events.count("opened"),1)
                stats=await campaign_popups.popup_stats({"username":"admin"},db)
                self.assertEqual(stats["campaigns"][campaign.id],{"displayed":1,"dismissed":1,"opened":1,"action_clicked":0})
                reset=await campaign_popups.reset_dismissals(campaign.id,{"username":"admin"},db)
                self.assertEqual(reset["dismissals_removed"],1)
                await campaign_popups.action_clicked(campaign.id,req,db)
                await campaign_popups.action_clicked(campaign.id,req,db)
                token2="popup-track-2";portal_sessions[token2]=user.id
                self.assertIsNone((await campaign_popups.login_popup(request(token2),db))["promotion"])
                self.assertEqual((await db.execute(select(func.count(CampaignReadState.id)))).scalar(),1)
                portal_sessions.pop(token,None);portal_sessions.pop(token2,None);popup_evaluated_sessions.discard(token2)
            await engine.dispose()
        asyncio.run(scenario())

    def test_empty_poll_does_not_consume_session(self):
        async def scenario():
            engine=create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
            sessions=async_sessionmaker(engine,expire_on_commit=False)
            async with sessions() as db:
                client=Client(name="Polling",email="polling@popup.test",subdomain="popup-polling",status=ClientStatus.ACTIVE)
                db.add(client);await db.flush()
                user=ClientUser(client_id=client.id,name="Polling",email="polling-user@popup.test",password_hash="x",is_active=True)
                db.add(user);await db.flush();db.add(ClientOnboardingState(client_user_id=user.id,onboarding_version="rc1.4.3",status="skipped"));await db.commit()
                token="popup-empty-poll";portal_sessions[token]=user.id
                self.assertIsNone((await campaign_popups.login_popup(request(token),db))["promotion"])
                self.assertNotIn(token,popup_evaluated_sessions)
                campaign=Campaign(internal_name="live-poll",title="Live",campaign_type="promotion",body_content="Body",status="published",published_at=campaigns.now_utc(),created_by="admin",updated_by="admin",target_all_clients=True,popup_enabled=True)
                db.add(campaign);await db.commit()
                self.assertEqual((await campaign_popups.login_popup(request(token),db))["promotion"]["id"],campaign.id)
                portal_sessions.pop(token,None);popup_evaluated_sessions.discard(token)
            await engine.dispose()
        asyncio.run(scenario())

    def test_endpoints_require_authentication(self):
        app=FastAPI();app.include_router(campaign_popups.router)
        client=TestClient(app)
        self.assertEqual(client.get("/api/portal/promotions/login-popup").status_code,401)
        self.assertEqual(client.get("/api/admin/campaign-popup-stats").status_code,401)

    def test_action_url_policy_and_popup_payload(self):
        for allowed in (None,"/portal","/portal/whats-new?campaign_id=1","/portal/getting-started","https://example.com/path"):
            self.assertTrue(campaigns.valid_action_url(allowed))
        for rejected in ("http://example.com","javascript:alert(1)","//example.com","/portal/logout","https://user:pass@example.com"):
            self.assertFalse(campaigns.valid_action_url(rejected))
        campaign=Campaign(id=3,title="Offer",subtitle="Subtitle",campaign_type="promotion",body_content="Body",call_to_action_label="Open",call_to_action_url="https://example.com",image_reference="image.png")
        payload=campaign_popups.popup_payload(campaign)
        self.assertEqual(payload["summary"],"Subtitle")
        self.assertEqual(payload["call_to_action_label"],"Open")
        self.assertNotIn("internal_name",payload)

    def test_frontend_contract(self):
        popup=(ROOT/"app/static/campaign-popup.js").read_text()
        portal=(ROOT/"app/routers/portal.py").read_text()
        admin=(ROOT.parent/"frontend/src/pages/Campaigns.jsx").read_text()
        self.assertIn("login-promotion-modal",portal)
        self.assertIn("Enable popup notification",admin)
        self.assertIn("Every published campaign appears in What’s New.",admin)
        self.assertIn("Delivery summary",admin)
        self.assertIn("Publish immediately",admin)
        self.assertIn("browser local timezone",admin)
        self.assertIn("stored as UTC",admin)
        self.assertIn("30-second polling is the fallback",admin)
        self.assertIn("delivery_status",(ROOT/"app/routers/campaigns.py").read_text())
        self.assertIn("Schedule for later",admin)
        self.assertIn("No automatic end date",admin)
        self.assertIn("less than one hour",admin)
        self.assertIn("Campaign published successfully.",admin)
        self.assertIn("Current recipient estimate",admin)
        self.assertIn("Eligible recipients",admin)
        self.assertIn("campaign-audience",admin)
        self.assertIn("Select at least one client before publishing",admin)
        self.assertIn("Resend popup notification?",admin)
        self.assertIn('e.key==="Escape"',popup)
        self.assertIn('e.key!=="Tab"',popup)
        self.assertIn('POLL_MS=30000',popup)
        self.assertIn('setInterval',popup)
        self.assertIn('campaign-popup-open',popup)
        self.assertIn('.campaign-modal-backdrop {{ position:fixed; inset:0; z-index:80',portal)
        self.assertIn('@media (max-width:390px)',portal)
        self.assertIn('setInterval',(ROOT/"app/static/campaigns-client.js").read_text())
        self.assertIn('campaignStatusInterval=30000',portal)
        self.assertIn("badge.classList.toggle('hidden',!count)",portal)
        self.assertIn("nav.classList.toggle('campaign-nav-unread',!!count)",portal)
        self.assertIn("campaign-unread-banner",portal)
        self.assertIn("You have 1 new announcement.",portal)
        self.assertIn("body.onboarding-active #campaign-unread-banner",portal)
        self.assertIn('document.addEventListener("visibilitychange"',popup)
        self.assertIn('.campaign-unread-pulse {{ animation:none !important; }}',portal)
        migration=(ROOT/"migrations/20260722_clear_pre_overlay_popup_impressions.sql").read_text()
        self.assertIn("event_type = 'displayed'",migration)
        self.assertNotIn("event_type = 'dismissed'",migration)
        deploy=(ROOT.parent/"deploy/scripts/deploy_platform.sh").read_text()
        self.assertIn('20260722_clear_pre_overlay_popup_impressions.sql',deploy)
        self.assertNotIn("innerHTML",popup)


if __name__=="__main__":
    unittest.main()
