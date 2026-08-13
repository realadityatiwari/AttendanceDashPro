import hashlib
import secrets
import hmac
from datetime import datetime, timedelta, timezone
import jwt
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored pbkdf2_sha256 hash."""
    if not hashed_password or not hashed_password.startswith("pbkdf2_sha256$"):
        return False
        
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3:
            return False
            
        _, salt, stored_key_hex = parts
        
        # Hash the incoming password with the same salt
        computed_key = hashlib.pbkdf2_hmac(
            'sha256', 
            plain_password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        )
        
        # Compare securely
        return hmac.compare_digest(stored_key_hex, computed_key.hex())
    except Exception:
        return False

def create_access_token(subject: str, roll_number: str) -> str:
    """Creates a standard JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "exp": expire,
        "sub": subject,
        "roll_number": roll_number,
        "type": "access"
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt
