import asyncio,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from database import Base,get_db
from middleware import AdminAuthMiddleware
from models import Client,ClientStatus,ClientUser
from routers import campaigns,client_guides,portal,portal_users
from routers.portal_state import portal_sessions

class ClientPortalAuthenticationTests(unittest.TestCase):
 def setUp(self):
  portal_sessions.clear();portal_users.password_reset_tokens.clear();self.engine=create_async_engine('sqlite+aiosqlite:///:memory:');self.sessions=async_sessionmaker(self.engine,expire_on_commit=False);asyncio.run(self._seed())
  self.app=FastAPI();self.app.include_router(portal_users.router,prefix='/api/portal');self.app.include_router(portal.router);self.app.include_router(client_guides.router);self.app.include_router(campaigns.router);self.app.add_middleware(AdminAuthMiddleware)
  async def db_override():
   async with self.sessions() as db:
    try:yield db;await db.commit()
    except Exception:await db.rollback();raise
  self.app.dependency_overrides[get_db]=db_override;self.portal_session_patch=patch.object(portal,'async_session',self.sessions);self.portal_session_patch.start();self.email_patch=patch('email_service.send_password_reset_email',return_value=True);self.email_patch.start();self.client=TestClient(self.app,base_url='https://client.mybeacon.co.za')
 def tearDown(self):
  self.email_patch.stop();self.portal_session_patch.stop();portal_sessions.clear();portal_users.password_reset_tokens.clear();asyncio.run(self.engine.dispose())
 async def _seed(self):
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
  async with self.sessions() as db:
   client=Client(name='Existing Client',email='owner@example.test',subdomain='existing',status=ClientStatus.ACTIVE);db.add(client);await db.flush();db.add(ClientUser(client_id=client.id,name='Existing User',email='user@example.test',password_hash=portal_users.hash_password('ValidPass123!'),role='admin',force_password_change=False,is_active=True));await db.commit()
 def test_valid_login_cookie_redirect_refresh_guides_and_logout(self):
  self.client.cookies.set('portal_token','stale-session',domain='client.mybeacon.co.za',path='/')
  response=self.client.post('/api/portal/auth/login',json={'email':'user@example.test','password':'ValidPass123!'})
  self.assertEqual(response.status_code,200);cookie=response.headers['set-cookie'];self.assertIn('portal_token=',cookie);self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=lax',cookie);self.assertIn('Path=/',cookie);self.assertNotIn('Domain=',cookie);self.assertNotIn('Max-Age=',cookie);self.assertNotIn('expires=',cookie.lower())
  token=self.client.cookies.get('portal_token');self.assertTrue(token);self.assertIn(token,portal_sessions)
  first=self.client.get('/portal',follow_redirects=False);self.assertEqual(first.status_code,200);self.assertIn('Account &amp; Support',first.text)
  refresh=self.client.get('/portal',follow_redirects=False);self.assertEqual(refresh.status_code,200)
  guides=self.client.get('/portal/guides',follow_redirects=False);self.assertEqual(guides.status_code,200);self.assertIn('Guides &amp; Help',guides.text)
  whats_new=self.client.get('/portal/whats-new',follow_redirects=False);self.assertEqual(whats_new.status_code,200)
  logout=self.client.get('/portal/logout',follow_redirects=False);self.assertEqual(logout.status_code,302);self.assertEqual(logout.headers['location'],'/portal/login');self.assertNotIn(token,portal_sessions);self.assertNotIn('portal_token',self.client.cookies)
  self.assertEqual(self.client.get('/portal',follow_redirects=False).status_code,302)
 def test_invalid_credentials_and_password_reset_remain_clear(self):
  invalid=self.client.post('/api/portal/auth/login',json={'email':'user@example.test','password':'wrong'});self.assertEqual(invalid.status_code,401);self.assertEqual(invalid.json()['detail'],'Invalid credentials')
  forgot=self.client.post('/api/portal/auth/forgot-password',json={'email':'user@example.test'});self.assertEqual(forgot.status_code,200);code=forgot.json()['debug_token']
  reset=self.client.post('/api/portal/auth/reset-password',json={'email':'user@example.test','token':code,'new_password':'NewValidPass123!'});self.assertEqual(reset.status_code,200)
  login=self.client.post('/api/portal/auth/login',json={'email':'user@example.test','password':'NewValidPass123!'});self.assertEqual(login.status_code,200);self.assertIn('portal_token=',login.headers['set-cookie'])
 def test_login_page_relies_on_server_cookie_not_javascript_cookie(self):
  page=self.client.get('/portal/login');self.assertEqual(page.status_code,200);self.assertIn("fetch('/api/portal/auth/login'",page.text);self.assertNotIn("document.cookie = 'portal_token='",page.text);self.assertIn('Invalid credentials',page.text)
if __name__=='__main__':unittest.main()
