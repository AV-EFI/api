from fastapi import APIRouter, HTTPException, Depends
from ..schemas.auth import Token,UserCredentials
from ..helpers.mock_auth import mock_pid_system_auth,create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from ..helpers.auth import verify_token


router = APIRouter()

@router.post("/av-efi/auth", response_model=Token)
async def authenticate_user(form_data: OAuth2PasswordRequestForm = Depends()):
    # Authenticate with PID system
    user_data = mock_pid_system_auth(form_data.username, form_data.password)
    
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate JWT token
    access_token, expires_at = create_access_token(user_data)
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_at=expires_at
    )

# Example protected endpoint
@router.get("/av-efi/protected")
async def protected_route(current_user: dict = Depends(verify_token)):
    return {"message": "Access granted", "user": current_user}

