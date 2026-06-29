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
            print(f"  disk_used_gb: {inst.disk_used_gb}")
            print(f"  disk_total_gb: {inst.disk_total_gb}")
            print(f"  disk_usage_percent: {inst.disk_usage_percent}")
            print()

asyncio.run(main())
