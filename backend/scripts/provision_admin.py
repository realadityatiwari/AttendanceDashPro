"""
Provision the ADMIN role for a specific user (Phase 6.5).

Explicit, operator-invoked tooling only — there is no API path that assigns
roles, so ADMIN can never be self-assigned. Every account defaults to
STUDENT; this script is the sole sanctioned way to grant ADMIN.

Usage:
    python scripts/provision_admin.py <roll_number>
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.enums import UserRole
from sqlalchemy import select


async def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/provision_admin.py <roll_number>")
        sys.exit(1)

    roll_number = sys.argv[1].strip()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.roll_number == roll_number))
        user = result.scalars().first()
        if user is None:
            print(f"ERROR: no user with roll_number '{roll_number}' found.")
            sys.exit(1)

        user.role = UserRole.ADMIN
        await session.commit()
        print(f"OK: {user.name} ({user.roll_number}) is now ADMIN.")


if __name__ == "__main__":
    asyncio.run(main())