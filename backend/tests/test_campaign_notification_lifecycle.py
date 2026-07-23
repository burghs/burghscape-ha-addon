import asyncio,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"app"))
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from starlette.requests import Request
from database import Base
from models import Campaign,CampaignPopupEvent,CampaignPopupState,CampaignReadState,Client,ClientStatus,ClientUser,ClientOnboardingState
from routers import campaign_popups,campaigns
from routers.portal_state import portal_sessions

def req(token):return Request({"type":"http","method":"GET","path":"/","headers":[(b"cookie",f"portal_token={token}".encode())]})
class CampaignNotificationLifecycleTests(unittest.TestCase):
 def test_impression_snooze_dismiss_and_revision(self):
  async def scenario():
   engine=create_async_engine("sqlite+aiosqlite:///:memory:")
   async with engine.begin() as c:await c.run_sync(Base.metadata.create_all)
   sessions=async_sessionmaker(engine,expire_on_commit=False)
   async with sessions() as db:
    client=Client(name="Client",email="notify@test",subdomain="notify",status=ClientStatus.ACTIVE);db.add(client);await db.flush()
    user=ClientUser(client_id=client.id,name="User",email="user@notify.test",password_hash="x",is_active=True);db.add(user);await db.flush();db.add(ClientOnboardingState(client_user_id=user.id,onboarding_version="rc1.4.3",status="skipped"))
    campaign=Campaign(internal_name="notice",title="Notice",campaign_type="promotion",body_content="Body",status="published",published_at=campaigns.now_utc(),created_by="admin",updated_by="admin",target_all_clients=True,popup_enabled=True,popup_behavior="next_login",delivery_revision=1);db.add(campaign);await db.commit()
    token="session-one";portal_sessions[token]=user.id;r=req(token)
    self.assertEqual((await campaign_popups.login_popup(r,db))["promotion"]["revision"],1)
    body=campaign_popups.Occurrence(occurrence_id="1:display-0001")
    await campaign_popups.displayed(campaign.id,body,r,db);await campaign_popups.displayed(campaign.id,body,r,db)
    self.assertEqual((await db.execute(select(func.count(CampaignPopupEvent.id)))).scalar(),1)
    self.assertIsNotNone((await campaign_popups.login_popup(r,db))["promotion"])
    await campaign_popups.snoozed(campaign.id,campaign_popups.Occurrence(occurrence_id="1:snooze-0001"),r,db)
    self.assertIsNone((await campaign_popups.login_popup(r,db))["promotion"])
    token2="session-two";portal_sessions[token2]=user.id;r2=req(token2)
    self.assertIsNotNone((await campaign_popups.login_popup(r2,db))["promotion"])
    await campaign_popups.dismissed(campaign.id,campaign_popups.Occurrence(occurrence_id="1:dismiss-0001"),r2,db)
    self.assertIsNone((await campaign_popups.login_popup(r2,db))["promotion"])
    self.assertEqual((await db.execute(select(func.count(CampaignReadState.id)))).scalar(),1)
    resend=await campaigns.resend_popup(campaign.id,{"username":"admin"},db);self.assertEqual(resend["delivery_revision"],2);self.assertEqual(resend["eligible_recipients"],1)
    self.assertEqual((await campaign_popups.login_popup(r2,db))["promotion"]["revision"],2)
    self.assertEqual((await db.execute(select(func.count(CampaignPopupState.id)))).scalar(),1)
    portal_sessions.pop(token,None);portal_sessions.pop(token2,None)
   await engine.dispose()
  asyncio.run(scenario())
 def test_security_and_client_contracts(self):
  self.assertFalse(campaigns.valid_action_url("javascript:alert(1)"));self.assertFalse(campaigns.valid_action_url("data:text/plain,x"));self.assertTrue(campaigns.valid_action_url("mailto:help@example.com"));self.assertTrue(campaigns.valid_action_url("tel:+27110000000"))
  js=(ROOT/"app/static/campaign-popup.js").read_text();portal=(ROOT/"app/routers/portal.py").read_text();stream=(ROOT/"app/routers/campaign_notifications.py").read_text()
  for value in ('new EventSource','POLL_MS=15000','"snooze"','"dismiss"','crypto.randomUUID','visibilitychange','check("load")','MyBeaconCampaignDiagnostics'):self.assertIn(value,js)
  self.assertIn("Remind me later",portal);self.assertIn("Dismiss / Mark as read",portal);self.assertIn("campaign-popup.js?v={build_commit}",portal);self.assertIn("portal_user(request, db)",stream)
  support=Campaign(id=12,delivery_revision=4,title="Support",campaign_type="promotion",body_content="Help",call_to_action_type="support",call_to_action_label="Open support ticket",call_to_action_url="/portal#support")
  payload=campaigns.client_payload(support,False);self.assertEqual(payload["call_to_action_url"],"/portal?support_campaign=12&revision=4#support");self.assertEqual(campaign_popups.popup_payload(support)["call_to_action_url"],payload["call_to_action_url"])
  details=(ROOT/"app/static/campaigns-client.js").read_text();self.assertIn("call_to_action_label",details);self.assertIn("action-clicked",details)
  self.assertIn("grid-template-columns:1fr",portal);self.assertIn("overflow-x:auto",portal);self.assertIn("prefers-reduced-motion: reduce",portal)
