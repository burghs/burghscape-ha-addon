#!/usr/bin/env python3
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def main():
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/burghscape.db")
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        from models import Client
        result = await session.execute(select(Client).where(Client.id == 8))
        client = result.scalars().first()
        if client and client.cloudflare_tunnel_id:
            tunnel_id = client.cloudflare_tunnel_id
            print(f"Deleting tunnel {tunnel_id} for client {client.name}")
            client.cloudflare_tunnel_id = None
            client.cloudflare_tunnel_token = None
            await session.commit()
            print("Tunnel removed from DB. Add-on will auto-create a new one on restart.")
        else:
            print("No tunnel found for client 8")


asyncio.run(main())
