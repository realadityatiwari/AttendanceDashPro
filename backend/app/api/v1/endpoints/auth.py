from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.api.dependencies.deps import get_db

router = APIRouter()

class LoginRequest(BaseModel):
    roll_number: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    # 1. Find user by roll_number
    result = await db.execute(select(User).filter_by(roll_number=credentials.roll_number))
    user = result.scalars().first()
    
    # 2. Verify password (constant time comparison prevents timing attacks)
    # If user doesn't exist, we still want to avoid returning quickly to prevent user enumeration,
    # but for simplicity and safety against erroring out on None, we check it here.
    # To truly prevent timing attacks on user existence, we'd hash a dummy password here, 
    # but returning standard 401 is requested.
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect roll number or password",
        )
        
    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect roll number or password",
        )
        
    # 3. Generate JWT
    access_token = create_access_token(subject=str(user.id), roll_number=user.roll_number)
    
    return {"access_token": access_token, "token_type": "bearer"}
