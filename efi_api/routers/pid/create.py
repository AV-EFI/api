from http.client import HTTPException
import os
from fastapi import APIRouter, Depends
import httpx 

from efi_api.helpers.auth import verify_token
from efi_api.helpers.pid_create_tranfrom import wrap_pid_data
from efi_api.core.config import settings


router = APIRouter()
url = settings.PID_SERVICE_URL

@router.post("/create", summary="Create PID", tags=["PID"])
async def create_pid(data: dict, prefix: str, suffix: str, current_user: dict = Depends(verify_token)):
    """
    Create a new PID with authentication required
    
    Args:
        data: Input object to be wrapped in the required format
        prefix: Prefix for the PID URL
        suffix: Suffix for the PID URL
        current_user: Authenticated user information
    
    Returns:
        dict: Response from PID creation request
    """
    # Get base URL from environment variables
    # pid_service_url = os.getenv("PID_SERVICE_URL")
    print(url)
    if not url:
        raise HTTPException(
            status_code=500,
            detail="PID service URL not configured in environment variables"
        )

    wrapped_data = wrap_pid_data(data)


    # Construct URL with query parameters
    full_url = f"{url}?prefix={prefix}&suffix={suffix}"
    
    # Create base64 encoded auth header
    import base64
    auth_string = f"{settings.PID_USERNAME}:{settings.PID_PASSWORD}"
    auth_bytes = auth_string.encode('ascii')
    base64_auth = base64.b64encode(auth_bytes).decode('ascii')
    headers = {'Authorization': f'Basic {base64_auth}'}

    print(base64_auth)
    # Make POST request to PID service with auth headers
    async with httpx.AsyncClient() as client:
        response = await client.post(full_url, json=wrapped_data, headers=headers)
        return response.json()
