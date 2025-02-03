from fastapi import HTTPException, Depends
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from ..core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="av-efi/auth")

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

async def get_auth_headers():
    """Helper function to generate authentication headers"""
    auth_string = f"{settings.PID_USERNAME}:{settings.PID_PASSWORD}"
    auth_bytes = auth_string.encode('ascii')
    base64_auth = base64.b64encode(auth_bytes).decode('ascii')
    return {'Authorization': f'Basic {base64_auth}'}