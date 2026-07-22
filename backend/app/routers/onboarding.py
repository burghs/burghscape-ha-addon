"""Authenticated, versioned Client Portal onboarding state."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import ClientOnboardingState
from routers.campaigns import portal_user

router=APIRouter()
CURRENT_ONBOARDING_VERSION="rc1.4.3"
MAX_STEP=7
TERMINAL={"completed","skipped"}

class StepUpdate(BaseModel):
    current_step:int=Field(ge=0,le=MAX_STEP)

def _iso(v): return v.isoformat() if v else None
def payload(s):
    if s is None: return {"onboarding_version":CURRENT_ONBOARDING_VERSION,"status":"not_started","current_step":0,"started_at":None,"completed_at":None,"skipped_at":None,"last_replay_at":None,"replay_active":False,"should_start":True}
    return {"onboarding_version":s.onboarding_version,"status":s.status,"current_step":s.current_step,"started_at":_iso(s.started_at),"completed_at":_iso(s.completed_at),"skipped_at":_iso(s.skipped_at),"last_replay_at":_iso(s.last_replay_at),"replay_active":s.replay_active,"should_start":s.status in {"not_started","in_progress"} or s.replay_active}

async def current_state(db,user_id):
    return (await db.execute(select(ClientOnboardingState).where(ClientOnboardingState.client_user_id==user_id,ClientOnboardingState.onboarding_version==CURRENT_ONBOARDING_VERSION))).scalars().first()
async def ensure_state(db,user_id):
    state=await current_state(db,user_id)
    if state is None:
        state=ClientOnboardingState(client_user_id=user_id,onboarding_version=CURRENT_ONBOARDING_VERSION);db.add(state);await db.flush()
    return state

@router.get("/api/portal/onboarding")
async def get_onboarding(request:Request,db:AsyncSession=Depends(get_db)):
    user=await portal_user(request,db);return payload(await current_state(db,user.id))

@router.post("/api/portal/onboarding/start")
async def start_onboarding(request:Request,db:AsyncSession=Depends(get_db)):
    user=await portal_user(request,db);state=await ensure_state(db,user.id)
    if state.status in TERMINAL and not state.replay_active: raise HTTPException(409,"Completed or skipped onboarding must be replayed explicitly")
    if state.status=="not_started": state.status,state.started_at,state.current_step="in_progress",datetime.utcnow(),0
    await db.commit();return payload(state)

@router.patch("/api/portal/onboarding/step")
async def save_step(body:StepUpdate,request:Request,db:AsyncSession=Depends(get_db)):
    user=await portal_user(request,db);state=await current_state(db,user.id)
    if not state or (state.status!="in_progress" and not state.replay_active): raise HTTPException(409,"Onboarding is not active")
    state.current_step=body.current_step;await db.commit();return payload(state)

@router.post("/api/portal/onboarding/skip")
async def skip_onboarding(request:Request,db:AsyncSession=Depends(get_db)):
    user=await portal_user(request,db);state=await ensure_state(db,user.id);now=datetime.utcnow()
    if state.replay_active: state.replay_active=False
    elif state.status!="completed": state.status,state.skipped_at="skipped",state.skipped_at or now
    state.current_step=0;await db.commit();return payload(state)

@router.post("/api/portal/onboarding/complete")
async def complete_onboarding(request:Request,db:AsyncSession=Depends(get_db)):
    user=await portal_user(request,db);state=await current_state(db,user.id)
    if not state or (state.status not in {"in_progress","completed"} and not state.replay_active): raise HTTPException(409,"Onboarding must be started before completion")
    if state.status!="completed": state.status,state.completed_at="completed",datetime.utcnow()
    state.replay_active,state.current_step=False,MAX_STEP;await db.commit();return payload(state)

@router.post("/api/portal/onboarding/replay")
async def replay_onboarding(request:Request,db:AsyncSession=Depends(get_db)):
    user=await portal_user(request,db);state=await ensure_state(db,user.id)
    if state.status not in TERMINAL: raise HTTPException(409,"Finish or skip initial onboarding before replaying")
    state.replay_active,state.last_replay_at,state.current_step=True,datetime.utcnow(),0;await db.commit();return payload(state)
