"""RC1.4.2 login-popup eligibility, interaction tracking, and admin metrics."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, distinct, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin_auth import get_current_admin
from database import get_db
from models import Campaign, CampaignPopupEvent, CampaignReadState
from routers.campaigns import now_utc, portal_user, visible_campaign, visible_clause
from routers.portal_state import popup_evaluated_sessions

router = APIRouter()
EVENTS = {"displayed", "dismissed", "opened", "action_clicked"}


def popup_payload(campaign: Campaign) -> dict:
    summary = campaign.popup_summary or campaign.subtitle or campaign.body_content[:240]
    has_action = bool(campaign.call_to_action_label and campaign.call_to_action_url)
    return {
        "id": campaign.id,
        "title": campaign.title,
        "summary": summary,
        "campaign_type": campaign.campaign_type,
        "image_url": f"/api/portal/campaigns/{campaign.id}/image" if campaign.image_reference else None,
        "details_url": f"/portal/whats-new?campaign_id={campaign.id}",
        "call_to_action_label": campaign.call_to_action_label if has_action else None,
        "call_to_action_url": campaign.call_to_action_url if has_action else None,
    }


def blocked_event(user_id: int):
    return exists(select(CampaignPopupEvent.id).where(
        CampaignPopupEvent.campaign_id == Campaign.id,
        CampaignPopupEvent.client_user_id == user_id,
        CampaignPopupEvent.event_type.in_(("dismissed", "action_clicked")),
    ))


@router.get("/api/portal/promotions/login-popup")
async def login_popup(request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db)
    token = request.cookies.get("portal_token", "")
    if not token or token in popup_evaluated_sessions:
        return {"promotion": None}
    popup_evaluated_sessions.add(token)
    campaign = (await db.execute(
        select(Campaign).where(
            visible_clause(user.client_id, now_utc()),
            Campaign.popup_enabled == True,
            ~blocked_event(user.id),
        ).order_by(Campaign.priority.desc(), Campaign.starts_at.desc().nullslast(), Campaign.id.desc()).limit(1)
    )).scalars().first()
    return {"promotion": popup_payload(campaign) if campaign else None}


async def available_popup(db: AsyncSession, campaign_id: int, user):
    campaign = await visible_campaign(db, campaign_id, user)
    if not campaign or not campaign.popup_enabled:
        raise HTTPException(404, "Promotion not found")
    return campaign


async def add_read_state(db: AsyncSession, campaign_id: int, user_id: int):
    present = (await db.execute(select(CampaignReadState.id).where(
        CampaignReadState.campaign_id == campaign_id,
        CampaignReadState.client_user_id == user_id,
    ))).scalar()
    if not present:
        db.add(CampaignReadState(campaign_id=campaign_id, client_user_id=user_id, read_at=now_utc()))


async def track(request: Request, db: AsyncSession, campaign_id: int, event_type: str):
    if event_type not in EVENTS:
        raise HTTPException(422, "Invalid popup event")
    user = await portal_user(request, db)
    campaign = await available_popup(db, campaign_id, user)
    if event_type == "action_clicked" and not (campaign.call_to_action_label and campaign.call_to_action_url):
        raise HTTPException(409, "Promotion has no primary action")
    if event_type in {"dismissed", "action_clicked"}:
        present = (await db.execute(select(CampaignPopupEvent.id).where(
            CampaignPopupEvent.campaign_id == campaign_id,
            CampaignPopupEvent.client_user_id == user.id,
            CampaignPopupEvent.event_type == event_type,
        ))).scalar()
        if present:
            return {"status": event_type}
    db.add(CampaignPopupEvent(campaign_id=campaign_id, client_user_id=user.id, event_type=event_type, occurred_at=now_utc()))
    if event_type in {"opened", "action_clicked"}:
        await add_read_state(db, campaign_id, user.id)
    await db.commit()
    return {"status": event_type}


@router.post("/api/portal/promotions/{campaign_id}/displayed")
async def displayed(campaign_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    return await track(request, db, campaign_id, "displayed")


@router.post("/api/portal/promotions/{campaign_id}/dismiss")
async def dismissed(campaign_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    return await track(request, db, campaign_id, "dismissed")


@router.post("/api/portal/promotions/{campaign_id}/opened")
async def opened(campaign_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    return await track(request, db, campaign_id, "opened")


@router.post("/api/portal/promotions/{campaign_id}/action-clicked")
async def action_clicked(campaign_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    return await track(request, db, campaign_id, "action_clicked")


@router.get("/api/admin/campaign-popup-stats")
async def popup_stats(admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(
        CampaignPopupEvent.campaign_id,
        CampaignPopupEvent.event_type,
        func.count(CampaignPopupEvent.id),
        func.count(distinct(CampaignPopupEvent.client_user_id)),
    ).group_by(CampaignPopupEvent.campaign_id, CampaignPopupEvent.event_type))).all()
    result = {}
    for campaign_id, event_type, event_count, user_count in rows:
        values = result.setdefault(campaign_id, {"displayed": 0, "dismissed": 0, "opened": 0, "action_clicked": 0})
        values[event_type] = event_count if event_type == "displayed" else user_count
    return {"campaigns": result}


@router.post("/api/admin/campaigns/{campaign_id}/reset-popup-dismissals")
async def reset_dismissals(campaign_id: int, admin: dict = Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    campaign = (await db.execute(select(Campaign.id).where(Campaign.id == campaign_id))).scalar()
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    result = await db.execute(delete(CampaignPopupEvent).where(
        CampaignPopupEvent.campaign_id == campaign_id,
        CampaignPopupEvent.event_type == "dismissed",
    ))
    await db.commit()
    return {"status": "reset", "dismissals_removed": result.rowcount or 0}
