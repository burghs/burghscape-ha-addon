#!/usr/bin/env python3
import asyncio
from sqlalchemy import select
from database import async_session
from models import HomeAssistantInstance

async def main():
    async with async_session() as db:
        result = await db.execute(select(HomeAssistantInstance))
        instances = result.scalars().all()
        for inst in instances:
            print(f"ID: {inst.id}, Name: {inst.name}")
            print(f"  updates_available: {inst.updates_available}")
            print(f"  type: {type(inst.updates_available)}")
            if inst.updates_available:
                print(f"  count: {len(inst.updates_available)}")
                for u in inst.updates_available[:3]:
                    print(f"    - {u}")
            print()

asyncio.run(main())
