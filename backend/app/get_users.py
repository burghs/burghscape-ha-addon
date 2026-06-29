import asyncio
import sys
sys.path.insert(0, '/app')
from database import async_session
from sqlalchemy import select, text

async def main():
    async with async_session() as db:
        result = await db.execute(text("SELECT username, role, password_hash FROM users"))
        rows = result.fetchall()
        for r in rows:
            print(f"{r[0]} | {r[1]} | {r[2][:30]}")

asyncio.run(main())
