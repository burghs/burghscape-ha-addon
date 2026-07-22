"""Authenticated campaign availability stream with polling as client fallback."""
import asyncio
from collections import defaultdict
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from routers.campaigns import portal_user

router = APIRouter()
_subscribers: dict[int, set[asyncio.Queue]] = defaultdict(set)

async def notify_campaign_available():
    for queues in list(_subscribers.values()):
        for queue in list(queues):
            if queue.empty():
                queue.put_nowait("campaign-available")

@router.get("/api/portal/promotions/events")
async def campaign_events(request: Request, db: AsyncSession = Depends(get_db)):
    user = await portal_user(request, db)
    queue = asyncio.Queue(maxsize=1)
    _subscribers[user.id].add(queue)
    async def stream():
        try:
            yield "retry: 3000\nevent: ready\ndata: connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"event: {event}\ndata: check\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                if await request.is_disconnected():
                    break
        finally:
            _subscribers[user.id].discard(queue)
            if not _subscribers[user.id]:
                _subscribers.pop(user.id, None)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no"})
