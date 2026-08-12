import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT conname, contype, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'attendance_records'::regclass OR conrelid = 'users'::regclass OR conrelid = 'laboratory_records'::regclass;"))
        for row in res:
            print(row)

asyncio.run(main())
