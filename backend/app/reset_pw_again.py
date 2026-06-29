#!/usr/bin/env python3
import asyncio
from database import async_session, engine
from sqlalchemy import text
from routers.portal_users import hash_password

async def main():
    pw = "Beacon2026!"
    new_hash = hash_password(pw)
    print(f"Hashing {pw} -> {new_hash}")
    
    async with engine.begin() as conn:
        await conn.execute(text(
            "UPDATE client_users SET password_hash = :hash, force_password_change = false WHERE email = 'kenmyb@gmail.com'"
        ), {"hash": new_hash})
    
    # Verify
    from sqlalchemy import select
    from models import ClientUser
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT password_hash FROM client_users WHERE email = 'kenmyb@gmail.com'"))
        row = result.fetchone()
        print(f"Stored: {row[0]}")
        print(f"Match: {row[0] == new_hash}")

asyncio.run(main())
