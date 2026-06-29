#!/usr/bin/env python3
import asyncio
from sqlalchemy import update
from database import async_session
from models import ClientUser
from routers.portal_users import hash_password

async def main():
    async with async_session() as db:
        new_pw = "Beacon2026!"
        new_hash = hash_password(new_pw)
        await db.execute(
            update(ClientUser)
            .where(ClientUser.email == "kenmyb@gmail.com")
            .values(password_hash=new_hash, force_password_change=False)
        )
        await db.commit()
        print(f"Password reset to: {new_pw}")
        print(f"New hash: {new_hash}")

asyncio.run(main())
