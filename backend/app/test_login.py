#!/usr/bin/env python3
import asyncio
from database import async_session
from models import ClientUser
from sqlalchemy import select
from routers.portal_users import verify_password, hash_password

async def main():
    async with async_session() as db:
        result = await db.execute(select(ClientUser).where(ClientUser.email == "kenmyb@gmail.com"))
        user = result.scalars().first()
        stored = user.password_hash
        
        pw = "Beacon2026!"
        print(f"Stored: {stored[:50]}...")
        result = verify_password(pw, stored)
        print(f"Verify result: {result}")
        
        # Generate new hash and immediately verify
        new_hash = hash_password(pw)
        print(f"New hash: {new_hash[:50]}...")
        result2 = verify_password(pw, new_hash)
        print(f"New verify: {result2}")

asyncio.run(main())
