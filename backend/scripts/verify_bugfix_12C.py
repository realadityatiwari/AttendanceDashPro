import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx
from sqlalchemy import select
from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User

async def main() -> int:
    async with AsyncSessionLocal() as db:
        admin_user = (await db.execute(select(User).where(User.role == "ADMIN"))).scalars().first()
    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/analytics/overview", headers=headers)
        ov = r.json()
        bcs058 = next(s for s in ov["subjects"] if s["subject_code"] == "BCS-058")
        print(f"BCS-058 Lecture total: {bcs058['lecture']['total']}")
        print(f"BCS-058 Lecture attended: {bcs058['lecture']['attended']}")
        print(f"BCS-058 Lecture percentage: {bcs058['current_lecture_pct']}")
        print(f"BCS-058 Tutorial total: {bcs058['tutorial']['total']}")
        print(f"BCS-058 Tutorial attended: {bcs058['tutorial']['attended']}")
        print(f"BCS-058 Tutorial percentage: {bcs058['current_tutorial_pct']}")
        print(f"BCS-058 overall/current_avg_pct: {bcs058['current_avg_pct']}")
        
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
