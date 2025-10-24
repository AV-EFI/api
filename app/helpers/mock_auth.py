from datetime import datetime, timedelta
from typing import Optional
from ..core.config import settings
from jose import jwt, JWTError

def mock_pid_system_auth(username: str, password: str) -> Optional[dict]:
    """
    Simulate PID system authentication.
    In production, this would make an actual call to the PID system.
    """
    # Mock user database
    valid_users = {
        "username": {
            "password": "password",
            "roles": ["reviewer"]
        }
    }
    
    if username in valid_users and valid_users[username]["password"] == password:
        return {
            "sub": username,
            "roles": valid_users[username]["roles"]
        }
    return None

def create_access_token(data: dict) -> tuple[str, datetime]:
    """Create JWT token with expiry"""
    expires_at = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    to_encode.update({"exp": expires_at})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt, expires_at