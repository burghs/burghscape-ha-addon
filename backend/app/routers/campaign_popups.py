"""Revision-aware campaign notification selection, interaction state, and analytics."""
from datetime import timedelta
from hashlib import sha256
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from admin_auth import get_current_admin
from database import get_db
from models import Campaign, CampaignPopupEvent, CampaignPopupState, CampaignReadState
from routers.onboarding import current_state
from routers.campaigns import now_utc, portal_user, visible_campaign, visible_clause

router=APIRouter()
EVENTS={"displayed","snoozed","dismissed","opened","action_clicked"}

class Occurrence(BaseModel):
    occurrence_id: str = Field(min_length=8,max_length=64)

def session_hash(request):
    return sha256(request.cookies.get("portal_token","").encode()).hexdigest()

def popup_payload(c):
    has=bool(c.call_to_action_label and c.call_to_action_url)
    action_url=f"/portal/whats-new?campaign_id={c.id}" if c.call_to_action_type=="details" else c.call_to_action_url
    return {"id":c.id,"revision":c.delivery_revision,"title":c.title,"summary":c.popup_summary or c.subtitle or c.body_content[:240],"campaign_type":c.campaign_type,"popup_behavior":c.popup_behavior,"image_url":f"/api/portal/campaigns/{c.id}/image" if c.image_reference else None,"details_url":f"/portal/whats-new?campaign_id={c.id}","call_to_action_label":c.call_to_action_label if has else None,"call_to_action_url":action_url if has else None}

async def state_for(db,campaign,user_id,create=False):
    state=(await db.execute(select(CampaignPopupState).where(CampaignPopupState.campaign_id==campaign.id,CampaignPopupState.client_user_id==user_id,CampaignPopupState.delivery_revision==campaign.delivery_revision))).scalars().first()
    if not state and create:
        state=CampaignPopupState(campaign_id=campaign.id,client_user_id=user_id,delivery_revision=campaign.delivery_revision)
        db.add(state);await db.flush()
    return state

def state_allows(c,state,request,now):
    if not state:return True
    if state.acknowledged_at:return False
    if c.popup_behavior=="once" and state.last_displayed_at:return False
    if state.snoozed_until and state.snoozed_until>now:return False
    if c.popup_behavior=="next_login" and state.snoozed_session_hash==session_hash(request):return False
    return True

@router.get("/api/portal/promotions/login-popup")
async def login_popup(request:Request,db:AsyncSession=Depends(get_db)):
    user=await portal_user(request,db)
    onboarding=await current_state(db,user.id)
    if onboarding is None or onboarding.status in {"not_started","in_progress"} or onboarding.replay_active:return {"promotion":None,"suppressed_by_onboarding":True}
    now=now_utc()
    campaigns=(await db.execute(select(Campaign).where(visible_clause(user.client_id,now),Campaign.popup_enabled==True).order_by(Campaign.priority.desc(),Campaign.id.desc()))).scalars().all()
    for campaign in campaigns:
        state=await state_for(db,campaign,user.id)
        if state_allows(campaign,state,request,now):return {"promotion":popup_payload(campaign)}
    return {"promotion":None}

async def available(db,campaign_id,user,revision):
    c=await visible_campaign(db,campaign_id,user)
    if not c or not c.popup_enabled or c.delivery_revision!=revision:raise HTTPException(404,"Notification revision not found")
    return c

async def read(db,c,user_id):
    exists=(await db.execute(select(CampaignReadState.id).where(CampaignReadState.campaign_id==c.id,CampaignReadState.client_user_id==user_id,CampaignReadState.delivery_revision==c.delivery_revision))).scalar()
    if not exists:db.add(CampaignReadState(campaign_id=c.id,client_user_id=user_id,delivery_revision=c.delivery_revision,read_at=now_utc()))

async def track(request,db,campaign_id,event_type,body):
    user=await portal_user(request,db);revision=body.occurrence_id.split(":",1)[0]
    try:revision=int(revision)
    except ValueError:raise HTTPException(422,"Occurrence revision is invalid")
    c=await available(db,campaign_id,user,revision)
    if event_type=="action_clicked" and not (c.call_to_action_label and c.call_to_action_url):raise HTTPException(409,"Notification has no primary action")
    state=await state_for(db,c,user.id,True);now=now_utc()
    existing=(await db.execute(select(CampaignPopupEvent.id).where(CampaignPopupEvent.campaign_id==c.id,CampaignPopupEvent.client_user_id==user.id,CampaignPopupEvent.delivery_revision==revision,CampaignPopupEvent.event_type==event_type,CampaignPopupEvent.occurrence_id==body.occurrence_id))).scalar()
    if existing:return {"status":event_type,"revision":revision}
    db.add(CampaignPopupEvent(campaign_id=c.id,client_user_id=user.id,delivery_revision=revision,event_type=event_type,occurrence_id=body.occurrence_id,occurred_at=now))
    if event_type=="displayed":state.last_displayed_at=now
    elif event_type=="snoozed":
        if c.popup_behavior=="next_login":state.snoozed_session_hash=session_hash(request);state.snoozed_until=None
        elif c.popup_behavior=="after_delay":state.snoozed_until=now+timedelta(minutes=c.reminder_delay_minutes or 1440)
        else:state.snoozed_until=now+timedelta(hours=1)
    elif event_type in {"dismissed","action_clicked","opened"}:
        state.acknowledged_at=now;state.acknowledgment_type=event_type;await read(db,c,user.id)
    await db.commit();return {"status":event_type,"revision":revision}

@router.post("/api/portal/promotions/{campaign_id}/displayed")
async def displayed(campaign_id:int,body:Occurrence,request:Request,db:AsyncSession=Depends(get_db)):return await track(request,db,campaign_id,"displayed",body)
@router.post("/api/portal/promotions/{campaign_id}/snooze")
async def snoozed(campaign_id:int,body:Occurrence,request:Request,db:AsyncSession=Depends(get_db)):return await track(request,db,campaign_id,"snoozed",body)
@router.post("/api/portal/promotions/{campaign_id}/dismiss")
async def dismissed(campaign_id:int,body:Occurrence,request:Request,db:AsyncSession=Depends(get_db)):return await track(request,db,campaign_id,"dismissed",body)
@router.post("/api/portal/promotions/{campaign_id}/opened")
async def opened(campaign_id:int,body:Occurrence,request:Request,db:AsyncSession=Depends(get_db)):return await track(request,db,campaign_id,"opened",body)
@router.post("/api/portal/promotions/{campaign_id}/action-clicked")
async def clicked(campaign_id:int,body:Occurrence,request:Request,db:AsyncSession=Depends(get_db)):return await track(request,db,campaign_id,"action_clicked",body)

@router.get("/api/admin/campaign-popup-stats")
async def stats(admin:dict=Depends(get_current_admin),db:AsyncSession=Depends(get_db)):
    rows=(await db.execute(select(CampaignPopupEvent.campaign_id,CampaignPopupEvent.delivery_revision,CampaignPopupEvent.event_type,func.count(CampaignPopupEvent.id),func.count(distinct(CampaignPopupEvent.client_user_id))).join(Campaign,Campaign.id==CampaignPopupEvent.campaign_id).where(CampaignPopupEvent.delivery_revision==Campaign.delivery_revision).group_by(CampaignPopupEvent.campaign_id,CampaignPopupEvent.delivery_revision,CampaignPopupEvent.event_type))).all();result={}
    for cid,rev,event,total,users in rows:
        values=result.setdefault(cid,{"revision":rev,"displayed":0,"snoozed":0,"dismissed":0,"opened":0,"action_clicked":0})
        if rev==values["revision"]:values[event]=total if event in {"displayed","snoozed"} else users
    return {"campaigns":result}
