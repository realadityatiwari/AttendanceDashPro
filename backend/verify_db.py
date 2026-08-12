import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def verify_db():
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            print(f"DATABASE CONNECTIVITY VERIFIED: {result.scalar() == 1}")
    except Exception as e:
        print(f"DATABASE CONNECTION FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(verify_db())
