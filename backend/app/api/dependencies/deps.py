from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal

security = HTTPBearer()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Firebase Authentication Boundary.
    
    This is a structural dependency for verifying a Firebase ID token
    and returning the associated User from the database.
    
    Currently, Firebase Admin is not configured in this Phase 3 environment.
    To avoid insecure fake authentication, this endpoint safely fails with 501.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Firebase authentication is not yet connected to the backend. Setup Firebase Admin SDK to proceed."
    )
    
    # FUTURE IMPLEMENTATION:
    # token = credentials.credentials
    # try:
    #     decoded_token = auth.verify_id_token(token)
    #     firebase_uid = decoded_token['uid']
    # except Exception:
    #     raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    #
    # user = await db.execute(select(User).filter_by(firebase_uid=firebase_uid))
    # user = user.scalars().first()
    # if not user:
    #     raise HTTPException(status_code=404, detail="User not found")
    # return user
