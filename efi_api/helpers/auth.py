from fastapi import HTTPException, Depends
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from ..core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="av-efi/auth")

# Utility function to verify token for protected endpoints
async def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )