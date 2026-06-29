#!/usr/bin/env python3
import asyncio
from sqlalchemy import select
from database import async_session
from models import ClientUser
import hashlib

async def main():
    async with async_session() as db:
        result = await db.execute(select(ClientUser).where(ClientUser.email == "kenmyb@gmail.com"))
        user = result.scalars().first()
        if user:
            print(f"Hash: {user.password_hash[:60]}")
            print(f"Hash length: {len(user.password_hash)}")
            # Try to figure out the format
            if ":" in user.password_hash:
                parts = user.password_hash.split(":")
                print(f"Parts: {len(parts)}")
                print(f"Algorithm: {parts[0]}")
            else:
                # Maybe it's just a plain hash or base64
                print("No colon found")
            
            # Test common passwords
            for pw in ["Beacon2026!", "burghscape", "admin", "password", "Beacon2026", "mybeacon"]:
                # Try sha256
                h = hashlib.sha256(pw.encode()).hexdigest()
                if h == user.password_hash:
                    print(f"MATCH (sha256): {pw}")
                    break
                # Try sha256 with salt
                if ":" in user.password_hash:
                    salt, stored_hash = user.password_hash.split(":", 1)
                    h2 = hashlib.sha256((salt + pw).encode()).hexdigest()
                    if h2 == stored_hash:
                        print(f"MATCH (sha256 salted): {pw}")
                        break
                    h3 = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 100000).hex()
                    if h3 == stored_hash:
                        print(f"MATCH (pbkdf2): {pw}")
                        break
            else:
                print("No common password matched")
        else:
            print("User not found")

asyncio.run(main())
