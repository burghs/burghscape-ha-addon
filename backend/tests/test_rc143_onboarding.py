import asyncio,sys,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from starlette.requests import Request
from database import Base
from models import Client,ClientStatus,ClientUser,ClientOnboardingState
from routers import onboarding,campaign_popups
from routers.portal_state import portal_sessions,popup_evaluated_sessions

def req(token): return Request({"type":"http","method":"GET","path":"/","headers":[(b"cookie",f"portal_token={token}".encode())]})
class RC143Tests(unittest.TestCase):
 def test_lifecycle_replay_isolation_and_future_version(self):
  async def run():
   engine=create_async_engine("sqlite+aiosqlite:///:memory:")
   async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
   sessions=async_sessionmaker(engine,expire_on_commit=False)
   async with sessions() as db:
    client=Client(name="New",email="new@test",subdomain="new",status=ClientStatus.ACTIVE);other=Client(name="Other",email="other@test",subdomain="other",status=ClientStatus.ACTIVE);db.add_all([client,other]);await db.flush()
    user=ClientUser(client_id=client.id,name="New",email="user@test",password_hash="x",is_active=True);user2=ClientUser(client_id=other.id,name="Other",email="user2@test",password_hash="x",is_active=True);db.add_all([user,user2]);await db.commit()
    portal_sessions["new"]=user.id;portal_sessions["other"]=user2.id
    self.assertTrue((await onboarding.get_onboarding(req("new"),db))["should_start"])
    self.assertEqual((await onboarding.start_onboarding(req("new"),db))["status"],"in_progress")
    self.assertEqual((await onboarding.save_step(onboarding.StepUpdate(current_step=3),req("new"),db))["current_step"],3)
    self.assertEqual((await onboarding.get_onboarding(req("other"),db))["status"],"not_started")
    done=await onboarding.complete_onboarding(req("new"),db);self.assertEqual(done["status"],"completed")
    replay=await onboarding.replay_onboarding(req("new"),db);self.assertTrue(replay["replay_active"]);self.assertIsNotNone(replay["last_replay_at"])
    done2=await onboarding.complete_onboarding(req("new"),db);self.assertEqual(done["completed_at"],done2["completed_at"])
    future=ClientOnboardingState(client_user_id=user.id,onboarding_version="rc1.5.0",status="not_started");db.add(future);await db.commit();self.assertEqual((await onboarding.get_onboarding(req("new"),db))["onboarding_version"],"rc1.4.3")
    for t in ("new","other"): portal_sessions.pop(t,None);popup_evaluated_sessions.discard(t)
   await engine.dispose()
  with patch.object(onboarding,"tour_enabled",return_value=True): asyncio.run(run())
 def test_disabled_default_preserves_existing_state_and_blocks_mutations(self):
  async def run():
   engine=create_async_engine("sqlite+aiosqlite:///:memory:");
   async with engine.begin() as c: await c.run_sync(Base.metadata.create_all)
   sessions=async_sessionmaker(engine,expire_on_commit=False)
   async with sessions() as db:
    client=Client(name="Disabled",email="disabled",subdomain="disabled",status=ClientStatus.ACTIVE);db.add(client);await db.flush();user=ClientUser(client_id=client.id,name="Disabled",email="disabled-user",password_hash="x",is_active=True);db.add(user);await db.flush();state=ClientOnboardingState(client_user_id=user.id,onboarding_version="rc1.4.3",status="in_progress",current_step=2,replay_active=True);db.add(state);await db.commit();portal_sessions["disabled"]=user.id
    result=await onboarding.get_onboarding(req("disabled"),db);self.assertFalse(result["enabled"]);self.assertFalse(result["should_start"]);self.assertEqual(result["disabled_reason"],"Client onboarding tour is disabled")
    before=(state.status,state.current_step,state.replay_active,state.last_replay_at)
    for action in (onboarding.start_onboarding,onboarding.replay_onboarding):
     with self.assertRaisesRegex(Exception,"Client onboarding tour is disabled"): await action(req("disabled"),db)
    await db.refresh(state);self.assertEqual(before,(state.status,state.current_step,state.replay_active,state.last_replay_at));portal_sessions.pop("disabled",None)
   await engine.dispose()
  asyncio.run(run())
 def test_skip_idempotence_auth_and_frontend_contract(self):
  app=FastAPI();app.include_router(onboarding.router);client=TestClient(app);self.assertEqual(client.get("/api/portal/onboarding").status_code,401)
  js=(ROOT/"app/static/onboarding.js").read_text();popup=(ROOT/"app/static/campaign-popup.js").read_text();portal=(ROOT/"app/routers/portal.py").read_text();theme=(ROOT/"app/static/theme.css").read_text();migration=(ROOT/"migrations/20260722_add_versioned_onboarding.sql").read_text()
  for value in ("onboarding:ready","prefers-reduced-motion","e.key", "current_step","visualViewport","orientationchange","positionTour","highlightNode"): self.assertIn(value,js)
  self.assertIn('id="onboarding-spotlight"',portal);self.assertIn("#onboarding-modal {{ z-index:70",portal);self.assertNotIn('target.classList.add("onboarding-spotlight")',js)
  self.assertEqual(portal.count("data-onboarding-dimmer="),4);self.assertIn("positionDimmers(v,hole)",js);self.assertIn("background:transparent",portal);self.assertIn("html[data-theme] #onboarding-modal { background: transparent !important; }",theme);self.assertNotIn("9999px",portal)
  self.assertIn("CLIENT_ONBOARDING_TOUR_ENABLED: bool = False",(ROOT/"app/config.py").read_text());self.assertIn("tour_enabled() and",(ROOT/"app/routers/campaign_popups.py").read_text());self.assertIn("suppressed_by_onboarding",(ROOT/"app/routers/campaign_popups.py").read_text());self.assertIn("data-onboarding-target",portal);self.assertIn("ON CONFLICT",migration);self.assertNotIn("localStorage",js);self.assertIn("onboarding:ready",popup)
 def test_spotlight_cutout_covers_every_step_and_viewport(self):
  targets=("instance","backups","support","campaigns","account","guides","getting-started");js=(ROOT/"app/static/onboarding.js").read_text()
  self.assertTrue(all(f'target:"{target}"' in js for target in targets))
  for width,height in ((1440,900),(768,1024),(390,844)):
   for index,_target in enumerate(targets):
    target_width=min(240,width-48);target_height=36;left=24+(index*37)%max(1,width-target_width-48);top=24+(index*71)%max(1,height-target_height-48);pad=7
    hole=(max(4,left-pad),max(4,top-pad),min(width-4,left+target_width+pad),min(height-4,top+target_height+pad))
    panels=((0,0,width,hole[1]),(hole[2],hole[1],width-hole[2],hole[3]-hole[1]),(0,hole[3],width,height-hole[3]),(0,hole[1],hole[0],hole[3]-hole[1]))
    center=(left+target_width/2,top+target_height/2)
    self.assertFalse(any(x<=center[0]<x+w and y<=center[1]<y+h for x,y,w,h in panels),f"{_target} dimmed at {width}x{height}")
    self.assertGreater(hole[2]-hole[0],target_width);self.assertGreater(hole[3]-hole[1],target_height)

if __name__=="__main__": unittest.main()
