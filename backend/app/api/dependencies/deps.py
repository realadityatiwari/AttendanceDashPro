from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import firebase_admin
from firebase_admin import auth
from app.db.session import AsyncSessionLocal
from app.models.user import User

security = HTTPBearer()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_firebase_identity(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Returns the verified Firebase UID and email without requiring the user to exist in the database.
    Used for profile synchronization (update).
    """
    if not firebase_admin._apps:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase Admin SDK is not initialized. Authentication is unavailable."
        )

    token = credentials.credentials
    try:
        decoded_token = auth.verify_id_token(token, check_revoked=True)
        return {
            "uid": decoded_token['uid'],
            "email": decoded_token.get('email', '')
        }
    except auth.RevokedIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    except auth.ExpiredIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except auth.InvalidIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

async def get_current_user(
    firebase_identity: dict = Depends(get_firebase_identity),
    db: AsyncSession = Depends(get_db)
):
    """
    Firebase Authentication Boundary.
    
    Verifies a Firebase ID token and returns the associated User from the database.
    Returns 404 if the verified Firebase user does not exist in the database.
    """
    firebase_uid = firebase_identity['uid']
    
    result = await db.execute(select(User).filter_by(firebase_uid=firebase_uid))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in application database. Account may not have been migrated.")
        
    return user
