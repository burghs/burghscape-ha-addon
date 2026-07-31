import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event,select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from admin_auth import get_current_admin
from database import Base,get_db
from models import Client,ClientGuide,ClientGuideAssignment,ClientStatus,ClientUser
from routers import client_guides
from routers.portal_state import portal_sessions

PNG=b'\x89PNG\r\n\x1a\n'+b'valid-image'
PDF=b'%PDF-1.7\nvalid-pdf'
class ClientGuidesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.engine=create_async_engine('sqlite+aiosqlite:///:memory:')
  @event.listens_for(self.engine.sync_engine,"connect")
  def _fk(dbapi_connection,_):dbapi_connection.execute("PRAGMA foreign_keys=ON")
  self.sessions=async_sessionmaker(self.engine,expire_on_commit=False)
  asyncio.run(self._seed());self.app=FastAPI();self.app.include_router(client_guides.router)
  async def db_override():
   async with self.sessions() as db:
    try: yield db;await db.commit()
    except Exception: await db.rollback();raise
  async def admin_override():return {'username':'admin','role':'superadmin'}
  self.app.dependency_overrides[get_db]=db_override;self.app.dependency_overrides[get_current_admin]=admin_override
  self.settings=type('S',(),{'GUIDE_MEDIA_ROOT':self.tmp.name,'GUIDE_MAX_UPLOAD_BYTES':128})()
  self.patch=patch('routers.client_guides.get_settings',return_value=self.settings);self.patch.start();self.client=TestClient(self.app)
 def tearDown(self):portal_sessions.clear();self.patch.stop();asyncio.run(self.engine.dispose());self.tmp.cleanup()
 async def _seed(self):
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
  async with self.sessions() as db:
   db.add_all([Client(id=1,name='Alpha',email='a@example.com',subdomain='alpha',status=ClientStatus.ACTIVE),Client(id=2,name='Beta',email='b@example.com',subdomain='beta',status=ClientStatus.ACTIVE),ClientUser(id=1,client_id=1,name='Viewer',email='v@example.com',password_hash='x',role='viewer',is_active=True),ClientUser(id=2,client_id=2,name='Other',email='o@example.com',password_hash='x',role='viewer',is_active=True)]);await db.commit()
 def create(self,data=None,file=PNG,mime='image/png',name='guide.png'):
  fields={'title':'Mobile setup','description':'Steps','category':'Setup','visibility_mode':'all','client_ids':'','published':'true','featured':'true','display_order':'1'};fields.update(data or {})
  return self.client.post('/api/admin/client-guides',data=fields,files={'guide_file':(name,file,mime)})
 def portal(self,user=1):portal_sessions['session']=user;return {'portal_token':'session'}
 def test_management_and_portal_authentication_required(self):
  app=FastAPI();app.include_router(client_guides.router);c=TestClient(app)
  self.assertEqual(c.get('/api/admin/client-guides').status_code,401);self.assertEqual(c.get('/api/portal/guides').status_code,401)
 def test_image_pdf_type_size_and_signature_validation(self):
  self.assertEqual(self.create().status_code,201);self.assertEqual(self.create(file=PDF,mime='application/pdf',name='guide.pdf').status_code,201)
  self.assertEqual(self.create(file=b'bad',mime='text/plain',name='bad.txt').status_code,415)
  self.assertEqual(self.create(file=b'x'*129,mime='image/png').status_code,413)
  self.assertEqual(self.create(file=b'not-png',mime='image/png').status_code,415)
 def test_visibility_publish_tenant_isolation_and_file_authorization(self):
  r=self.create({'visibility_mode':'selected','client_ids':'1'});gid=r.json()['id'];cookies=self.portal(1)
  self.assertEqual(len(self.client.get('/api/portal/guides',cookies=cookies).json()),1)
  self.assertEqual(self.client.get(f'/api/portal/guides/{gid}/file',cookies=cookies).status_code,200)
  cookies=self.portal(2);self.assertEqual(self.client.get('/api/portal/guides',cookies=cookies).json(),[]);self.assertEqual(self.client.get(f'/api/portal/guides/{gid}/file',cookies=cookies).status_code,404)
  data={k:v for k,v in r.json().items() if k in {'title','description','category','visibility_mode','client_ids','published','featured','display_order'}};data['published']=False
  self.assertEqual(self.client.put(f'/api/admin/client-guides/{gid}',json=data).status_code,200);cookies=self.portal(1);self.assertEqual(self.client.get('/api/portal/guides',cookies=cookies).json(),[])
 def test_replace_removes_old_and_delete_cascades_and_file(self):
  r=self.create();gid=r.json()['id'];old=list(Path(self.tmp.name).iterdir())[0]
  r=self.client.post(f'/api/admin/client-guides/{gid}/file',files={'guide_file':('new.pdf',PDF,'application/pdf')});self.assertEqual(r.status_code,200);self.assertFalse(old.exists());new=list(Path(self.tmp.name).iterdir())[0]
  self.assertEqual(self.client.delete(f'/api/admin/client-guides/{gid}').status_code,200);self.assertFalse(new.exists())
  async def counts():
   async with self.sessions() as db:return len((await db.execute(select(ClientGuide))).scalars().all()),len((await db.execute(select(ClientGuideAssignment))).scalars().all())
  self.assertEqual(asyncio.run(counts()),(0,0))
 def test_client_delete_removes_assignment_not_global_guide(self):
  gid=self.create({'visibility_mode':'selected','client_ids':'1'}).json()['id']
  async def remove():
   async with self.sessions() as db:
    c=(await db.execute(select(Client).where(Client.id==1))).scalar_one();await db.delete(c);await db.commit()
    return (await db.execute(select(ClientGuide).where(ClientGuide.id==gid))).scalar_one_or_none(),(await db.execute(select(ClientGuideAssignment))).scalars().all()
  guide,assignments=asyncio.run(remove());self.assertIsNotNone(guide);self.assertEqual(assignments,[])
 def test_frontend_and_spotlight_contract(self):
  management=(ROOT.parent/'frontend/src/pages/ClientGuides.jsx').read_text();portal=(ROOT/'app/routers/portal.py').read_text();viewer=(ROOT/'app/routers/client_guides.py').read_text();onboarding=(ROOT/'app/static/onboarding.js').read_text()
  for value in ('Upload Guide','Selected Clients','This action cannot be undone','Uploading…','editorError'):self.assertIn(value,management)
  nginx=(ROOT.parent/'frontend/nginx.conf').read_text();self.assertIn('location ^~ /api/admin/client-guides',nginx);self.assertIn('client_max_body_size 21m',nginx)
  self.assertIn('Guides &amp; Help',portal);self.assertIn('featured-guide-panel',portal);self.assertIn('guideSpotlightKey',portal);self.assertIn('localStorage',portal)
  self.assertIn('Guide PDF',viewer);self.assertIn('min-width:min(100%,900px)',viewer);self.assertNotIn('stored_file_name}</',viewer)
  self.assertIn('target:"guides"',onboarding);self.assertEqual(__import__('routers.onboarding',fromlist=['MAX_STEP']).MAX_STEP,8)
if __name__=='__main__':unittest.main()
