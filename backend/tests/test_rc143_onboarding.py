import asyncio,sys,unittest
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
  asyncio.run(run())
 def test_skip_idempotence_auth_and_frontend_contract(self):
  app=FastAPI();app.include_router(onboarding.router);client=TestClient(app);self.assertEqual(client.get("/api/portal/onboarding").status_code,401)
  js=(ROOT/"app/static/onboarding.js").read_text();popup=(ROOT/"app/static/campaign-popup.js").read_text();portal=(ROOT/"app/routers/portal.py").read_text();migration=(ROOT/"migrations/20260722_add_versioned_onboarding.sql").read_text()
  for value in ("onboarding:ready","prefers-reduced-motion","e.key", "current_step"): self.assertIn(value,js)
  self.assertIn("suppressed_by_onboarding",(ROOT/"app/routers/campaign_popups.py").read_text());self.assertIn("data-onboarding-target",portal);self.assertIn("ON CONFLICT",migration);self.assertNotIn("localStorage",js);self.assertIn("onboarding:ready",popup)
if __name__=="__main__": unittest.main()
