"""Dedicated sales leads created from client campaign interest."""
from datetime import datetime
from html import escape
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from admin_auth import get_current_admin
from database import get_db
from email_service import send_email
from models import Campaign, CampaignLead, CampaignLeadHistory, Client, ClientUser
from routers.campaigns import now_utc, portal_user, visible_campaign

router=APIRouter()
STATUSES=("new","contacted","quoted","scheduled","won","lost","cancelled")

class LeadCreate(BaseModel):
 comments: str = Field(default="",max_length=4000)
 preferred_contact_method: Literal["email","phone","whatsapp"]
 preferred_contact_time: str = Field(min_length=1,max_length=255)
class LeadUpdate(BaseModel):
 status: Literal["new","contacted","quoted","scheduled","won","lost","cancelled"]
 assigned_to: str|None = Field(default=None,max_length=255)
 internal_notes: str = Field(default="",max_length=10000)
 history_note: str = Field(default="",max_length=2000)

def payload(lead):
 return {"id":lead.id,"status":lead.status,"client_id":lead.client_id,"client_name":lead.client.name,"client_email":lead.client.email,"client_phone":lead.client.phone,"portal_user_name":lead.client_user.name if lead.client_user else None,"portal_user_email":lead.client_user.email if lead.client_user else None,"campaign_id":lead.campaign_id,"campaign_title":lead.campaign.title,"comments":lead.comments or "","preferred_contact_method":lead.preferred_contact_method,"preferred_contact_time":lead.preferred_contact_time,"assigned_to":lead.assigned_to,"internal_notes":lead.internal_notes or "","submitted_at":lead.submitted_at.isoformat(),"updated_at":lead.updated_at.isoformat(),"history":[{"from_status":h.from_status,"to_status":h.to_status,"changed_by":h.changed_by,"note":h.note,"changed_at":h.changed_at.isoformat()} for h in lead.history]}

def email_lead(lead):
 title=lead.campaign.title; client=lead.client; user=lead.client_user
 management=f"https://manage.mybeacon.co.za/campaign-leads?lead={lead.id}"
 comments=lead.comments or "No comments supplied"
 sales_text=f"Client: {user.name if user else client.name}\nCompany: {client.name}\nEmail: {user.email if user else client.email}\nPhone: {client.phone or 'Not supplied'}\nCampaign: {title}\nCampaign ID: {lead.campaign_id}\nSubmitted: {lead.submitted_at.isoformat()}\nPreferred contact: {lead.preferred_contact_method} — {lead.preferred_contact_time}\nComments: {comments}\nManagement: {management}"
 send_email("sales@burghscape.co.za",f"New Campaign Interest – {title}",f"<h2>New Campaign Interest</h2><pre>{escape(sales_text)}</pre><p><a href=\"{management}\">Open Campaign Lead</a></p>",sales_text)
 recipient=user.email if user else client.email
 client_text=f"Thank you for your interest in:\n\n{title}\n\nWe've received your request and a member of our team will contact you shortly to discuss implementation.\n\nIf you have additional information, simply reply to this email."
 send_email(recipient,"We've received your request",f"<p>Thank you for your interest in:</p><h2>{escape(title)}</h2><p>We've received your request and a member of our team will contact you shortly to discuss implementation.</p><p>If you have additional information, simply reply to this email.</p>",client_text)

@router.post("/api/portal/campaigns/{campaign_id}/interest",status_code=201)
async def create_lead(campaign_id:int,data:LeadCreate,request:Request,db:AsyncSession=Depends(get_db)):
 user=await portal_user(request,db);campaign=await visible_campaign(db,campaign_id,user)
 if not data.preferred_contact_time.strip(): raise HTTPException(422,"Preferred contact time is required")
 if not campaign: raise HTTPException(404,"Campaign not found")
 client=(await db.execute(select(Client).where(Client.id==user.client_id))).scalar_one()
 lead=CampaignLead(campaign_id=campaign.id,client_id=client.id,client_user_id=user.id,comments=data.comments.strip(),preferred_contact_method=data.preferred_contact_method,preferred_contact_time=data.preferred_contact_time.strip(),status="new")
 db.add(lead);await db.flush();db.add(CampaignLeadHistory(lead_id=lead.id,to_status="new",changed_by=f"client:{user.id}",note="Campaign interest submitted"));await db.commit();await db.refresh(lead)
 lead.campaign,lead.client,lead.client_user=campaign,client,user
 try:
  email_lead(lead)
 except Exception:
  import logging
  logging.getLogger("burghscape.campaign_leads").exception("Campaign lead email delivery failed for lead %s",lead.id)
 return {"id":lead.id,"status":"new","message":"We've received your request"}

def lead_query():
 return select(CampaignLead).join(CampaignLead.client).join(CampaignLead.campaign).outerjoin(CampaignLead.client_user).options(selectinload(CampaignLead.client),selectinload(CampaignLead.campaign),selectinload(CampaignLead.client_user),selectinload(CampaignLead.history))

@router.get("/api/admin/campaign-leads")
async def list_leads(search:str="",status:str="",assigned_to:str="",admin:dict=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
 q=lead_query()
 if status: q=q.where(CampaignLead.status==status)
 if assigned_to: q=q.where(CampaignLead.assigned_to==assigned_to)
 if search: q=q.where(or_(Client.name.ilike(f"%{search}%"),Campaign.title.ilike(f"%{search}%"),CampaignLead.comments.ilike(f"%{search}%")))
 leads=(await db.execute(q.order_by(CampaignLead.submitted_at.desc()))).scalars().unique().all()
 return {"leads":[payload(x) for x in leads]}

@router.get("/api/admin/campaign-leads/metrics")
async def metrics(admin:dict=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
 rows=dict((await db.execute(select(CampaignLead.status,func.count(CampaignLead.id)).group_by(CampaignLead.status))).all());total=sum(rows.values());won=rows.get("won",0);lost=rows.get("lost",0)
 return {"new":rows.get("new",0),"open":sum(rows.get(x,0) for x in ("new","contacted","quoted","scheduled")),"won":won,"lost":lost,"conversion_rate":round(won/(won+lost)*100,1) if won+lost else 0}

@router.get("/api/admin/campaign-leads/{lead_id}")
async def get_lead(lead_id:int,admin:dict=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
 q=lead_query().where(CampaignLead.id==lead_id);lead=(await db.execute(q)).scalars().unique().first()
 if not lead: raise HTTPException(404,"Campaign lead not found")
 return payload(lead)

@router.put("/api/admin/campaign-leads/{lead_id}")
async def update_lead(lead_id:int,data:LeadUpdate,admin:dict=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
 lead=(await db.execute(select(CampaignLead).where(CampaignLead.id==lead_id))).scalar_one_or_none()
 if not lead: raise HTTPException(404,"Campaign lead not found")
 old=lead.status;lead.status=data.status;lead.assigned_to=data.assigned_to.strip() if data.assigned_to else None;lead.internal_notes=data.internal_notes;lead.updated_at=datetime.utcnow()
 if old!=data.status or data.history_note: db.add(CampaignLeadHistory(lead_id=lead.id,from_status=old,to_status=data.status,changed_by=admin["username"],note=data.history_note))
 await db.commit();return await get_lead(lead.id,admin,db)
