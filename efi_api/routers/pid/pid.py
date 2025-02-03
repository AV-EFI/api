import os
from fastapi import APIRouter, Depends, Header, HTTPException  
from typing import Optional, List
import base64
import httpx
from efi_api.helpers.auth import verify_token
from efi_api.helpers.pid_create_tranfrom import wrap_pid_data
from efi_api.core.config import settings

router = APIRouter()
url = settings.PID_SERVICE_ADDRESS

TIMEOUT_SECONDS = 30.0

async def get_auth_headers():
    """Helper function to generate authentication headers"""
    auth_string = f"{settings.PID_USERNAME}:{settings.PID_PASSWORD}"
    auth_bytes = auth_string.encode('ascii')
    base64_auth = base64.b64encode(auth_bytes).decode('ascii')
    return {'Authorization': f'Basic {base64_auth}'}

@router.get("/handles/{pid}/{suffix}", summary="Get PID Handle", tags=["PID"])
async def get_pid_handle(
    pid: str,
    suffix: str,
    current_user: dict = Depends(verify_token)
):
    """
    Get a PID handle with authentication required
    
    Args:
        pid: PID identifier
        suffix: Suffix for the PID URL
        current_user: Authenticated user information
    
    Returns:
        dict: Response from PID service
    """
    if not url:
        raise HTTPException(
            status_code=500,
            detail="PID service URL not configured in environment variables"
        )
    
    full_url = f"{url}/handles/{pid}/{suffix}"
    print(full_url)
    headers = await get_auth_headers()
    
    async with httpx.AsyncClient() as client:
        response = await client.get(full_url, headers=headers)
        return response.json()

@router.put("/handles/{pid}/{suffix}", summary="Update PID Handle", tags=["PID"])
async def update_pid_handle(
    pid: str,
    suffix: str,
    data: List[dict],
    if_match: Optional[str] = Header(None),
    if_none_match: Optional[str] = Header(None),
    current_user: dict = Depends(verify_token)
):
    """
    Update a PID handle with authentication required
    
    Args:
        pid: PID identifier
        suffix: Suffix for the PID URL
        data: Input object to be wrapped in the required format
        if_match: Header for conditional requests (must be "*")
        if_none_match: Header for conditional requests (must be "*")
        current_user: Authenticated user information
    
    Returns:
        dict: Response from PID update request
    """
    if not url:
        raise HTTPException(
            status_code=500,
            detail="PID service URL not configured in environment variables"
        )
    print("I am here")
    
    
    # Validate headers
    if if_match is not None and if_match != "*":
        raise HTTPException(
            status_code=400,
            detail="If-Match header must be '*'"
        )
    
    if if_none_match is not None and if_none_match != "*":
        raise HTTPException(
            status_code=400,
            detail="If-None-Match header must be '*'"
        )
    
    # wrapped_data = wrap_pid_data(data)
    full_url = f"{url}/handles/{pid}/{suffix}"
    
    print("I am here")

    headers = await get_auth_headers()
    if if_match:
        headers['If-Match'] = if_match
    if if_none_match:
        headers['If-None-Match'] = if_none_match
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.put(full_url, json=data, headers=headers)
            return response.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Request to PID service timed out"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error communicating with PID service: {str(e)}"
        )

@router.delete("/handles/{pid}/{suffix}", summary="Delete PID Handle", tags=["PID"])
async def delete_pid_handle(
    pid: str,
    suffix: str,
    current_user: dict = Depends(verify_token)
):
    """
    Delete a PID handle with authentication required
    
    Args:
        pid: PID identifier
        suffix: Suffix for the PID URL
        current_user: Authenticated user information
    
    Returns:
        dict: Empty dict on successful deletion, error response otherwise
    """
    if not url:
        raise HTTPException(
            status_code=500,
            detail="PID service URL not configured in environment variables"
        )
    
    full_url = f"{url}/handles/{pid}/{suffix}"
    headers = await get_auth_headers()
    
    async with httpx.AsyncClient() as client:
        response = await client.delete(full_url, headers=headers)
        
        if response.status_code == 200:
            return {}
        else:
            # For any other status code, try to parse JSON response
            # If parsing fails, return the raw text
            try:
                return response.json()
            except:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.text
                )