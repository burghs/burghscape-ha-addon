import asyncio,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import async_sessionmaker,create_async_engine
from admin_auth import get_current_admin
from database import Base,get_db
from models import Campaign,CampaignLead,CampaignLeadHistory,Client,ClientStatus,ClientUser,SupportTicket
from routers import campaign_leads,campaigns
from routers.portal_state import portal_sessions

class CampaignLeadTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_async_engine('sqlite+aiosqlite:///:memory:');self.sessions=async_sessionmaker(self.engine,expire_on_commit=False);asyncio.run(self._seed())
  self.app=FastAPI();self.app.include_router(campaign_leads.router)
  async def db_override():
   async with self.sessions() as db:
    try:yield db
    except Exception:await db.rollback();raise
  async def admin_override():return {'username':'sales-admin','role':'superadmin'}
  self.app.dependency_overrides[get_db]=db_override;self.app.dependency_overrides[get_current_admin]=admin_override;self.client=TestClient(self.app);portal_sessions['lead-session']=1
 def tearDown(self):portal_sessions.clear();asyncio.run(self.engine.dispose())
 async def _seed(self):
  async with self.engine.begin() as c:await c.run_sync(Base.metadata.create_all)
  async with self.sessions() as db:
   db.add(Client(id=1,name='Alpha Company',email='office@alpha.test',phone='+27110000000',subdomain='alpha-lead',status=ClientStatus.ACTIVE));db.add(ClientUser(id=1,client_id=1,name='Alex Client',email='alex@alpha.test',password_hash='x',is_active=True));db.add(Campaign(id=1,internal_name='solar',title='Solar Automation',campaign_type='promotion',body_content='Body',status='published',published_at=campaigns.now_utc(),created_by='admin',updated_by='admin',target_all_clients=True,call_to_action_type='interest',call_to_action_label="I'm Interested"));await db.commit()
 def test_create_emails_no_ticket_status_assignment_search_filter(self):
  sent=[]
  with patch('routers.campaign_leads.send_email',side_effect=lambda *args:sent.append(args) or True):
   response=self.client.post('/api/portal/campaigns/1/interest',cookies={'portal_token':'lead-session'},json={'comments':'Please call about installation','preferred_contact_method':'phone','preferred_contact_time':'Weekdays after 14:00'})
  self.assertEqual(response.status_code,201);self.assertEqual(response.json()['status'],'new');self.assertEqual(len(sent),2);self.assertEqual(sent[0][0],'sales@burghscape.co.za');self.assertEqual(sent[0][1],'New Campaign Interest – Solar Automation');self.assertEqual(sent[1][0],'alex@alpha.test');self.assertEqual(sent[1][1],"We've received your request")
  async def counts():
   async with self.sessions() as db:return (await db.execute(select(func.count(CampaignLead.id)))).scalar(),(await db.execute(select(func.count(SupportTicket.id)))).scalar()
  self.assertEqual(asyncio.run(counts()),(1,0))
  lead_id=response.json()['id'];updated=self.client.put(f'/api/admin/campaign-leads/{lead_id}',json={'status':'contacted','assigned_to':'Sam Sales','internal_notes':'Follow up tomorrow','history_note':'Called client'});self.assertEqual(updated.status_code,200);data=updated.json();self.assertEqual(data['status'],'contacted');self.assertEqual(data['assigned_to'],'Sam Sales');self.assertEqual(len(data['history']),2)
  self.assertEqual(len(self.client.get('/api/admin/campaign-leads?search=Solar').json()['leads']),1);self.assertEqual(len(self.client.get('/api/admin/campaign-leads?status=contacted&assigned_to=Sam%20Sales').json()['leads']),1);self.assertEqual(self.client.get('/api/admin/campaign-leads?status=won').json()['leads'],[])
 def test_auth_visibility_validation_and_ui_contract(self):
  self.assertEqual(self.client.post('/api/portal/campaigns/1/interest',json={'comments':'','preferred_contact_method':'email','preferred_contact_time':'Morning'}).status_code,401)
  self.assertEqual(self.client.post('/api/portal/campaigns/1/interest',cookies={'portal_token':'lead-session'},json={'comments':'','preferred_contact_method':'email','preferred_contact_time':'   '}).status_code,422)
  ui=(ROOT.parent/'frontend/src/pages/CampaignLeads.jsx').read_text();layout=(ROOT.parent/'frontend/src/components/Layout.jsx').read_text();client=(ROOT/'app/static/campaigns-client.js').read_text();portal=(ROOT/'app/routers/portal.py').read_text()
  for value in ('Campaign Leads','Conversion Rate','Status history','Assigned to','Search leads'):self.assertIn(value,ui)
  self.assertIn('/campaign-leads',layout);self.assertIn('campaign-interest-form',client);self.assertIn('/interest',client);self.assertNotIn('support_campaign',portal)
if __name__=='__main__':unittest.main()
