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
    campaign.delivery_revision=2;await db.commit()
    self.assertEqual((await campaign_popups.login_popup(r2,db))["promotion"]["revision"],2)
    self.assertEqual((await db.execute(select(func.count(CampaignPopupState.id)))).scalar(),1)
    portal_sessions.pop(token,None);portal_sessions.pop(token2,None)
   await engine.dispose()
  asyncio.run(scenario())
 def test_security_and_client_contracts(self):
  self.assertFalse(campaigns.valid_action_url("javascript:alert(1)"));self.assertFalse(campaigns.valid_action_url("data:text/plain,x"));self.assertTrue(campaigns.valid_action_url("mailto:help@example.com"));self.assertTrue(campaigns.valid_action_url("tel:+27110000000"))
  js=(ROOT/"app/static/campaign-popup.js").read_text();portal=(ROOT/"app/routers/portal.py").read_text();stream=(ROOT/"app/routers/campaign_notifications.py").read_text()
  for value in ('new EventSource','POLL_MS=30000','"snooze"','"dismiss"','crypto.randomUUID','visibilitychange'):self.assertIn(value,js)
  self.assertIn("Remind me later",portal);self.assertIn("Dismiss",portal);self.assertIn("portal_user(request, db)",stream)
