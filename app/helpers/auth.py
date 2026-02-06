from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from starlette.requests import Request

from ..core.config import settings
from ..schemas.auth import Token

SESSION_TIMEOUT = 20 * 60       # Seconds of inactivity before forced logout


def is_expired(token: Annotated[dict, Token]) -> bool:
    current_time = int(datetime.utcnow().timestamp())
    if current_time - token.get('timestamp', 0) > SESSION_TIMEOUT:
        return True
    token['timestamp'] = current_time
    return False


def valid_access_token(request: Request):
    token = request.session.get('token')
    if not token or is_expired(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Not logged in'
        )
    return token


def has_role(role_name: str):
    async def check_role(
        token: Annotated[dict, Depends(valid_access_token)]
    ):
        if role_name not in token.get('scopes', []):
            raise HTTPException(status_code=403, detail='Unauthorized access')

    return check_role


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
