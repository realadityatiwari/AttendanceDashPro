import os
import sys
import asyncio
from pathlib import Path
import hashlib
import secrets

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select

def hash_password(password: str) -> str:
    # Use standard library hashlib's pbkdf2_hmac for safe password hashing without external dependencies.
    # It generates a salt, runs pbkdf2, and formats as salt$hash
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    )
    return f"pbkdf2_sha256${salt}${key.hex()}"

async def main():
    password = os.environ.get("INITIAL_PASSWORD")
    if not password:
        print("ERROR: INITIAL_PASSWORD environment variable not set.")
        sys.exit(1)
        
    uid = "HCRbV7Kld3Wo9IHLJHRGlBau4Mq2"
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.firebase_uid == uid))
        user = result.scalars().first()
        
        if not user:
            print(f"ERROR: User with firebase_uid '{uid}' not found.")
            sys.exit(1)
            
        print(f"User found: {user.name} ({user.roll_number})")
        
        # Idempotent update
        hashed = hash_password(password)
        user.hashed_password = hashed
        await session.commit()
        
        print("Password hash successfully generated and assigned.")

if __name__ == "__main__":
    asyncio.run(main())
