from http.client import HTTPException
from typing import Annotated

from fastapi import APIRouter, Body, Depends
import httpx

from app.core.config import settings
from app.helpers.auth import verify_token
from app.helpers.pid_create_tranfrom import wrap_pid_data

router = APIRouter()
url = settings.PID_SERVICE_URL


@router.put("/update/{handle_suffix}", summary="Update PID", tags=["PID"])
async def update_pid(
    handle_suffix: str,
    data: Annotated[
        dict,
        Body(
            ...,
            examples={"category": "SOME CATEGORY", "type": "SOME TYPE"},
            description="Minimum required data format",
        ),
    ],
    current_user: Annotated[dict, Depends(verify_token)],
):
    """Update an existing PID with authentication required.

    Parameters
    ----------
    handle_suffix : str
        The suffix of the handle to update.
    data : dict
        Input object to be wrapped in the required format.
    current_user : dict
        Authenticated user information.

    Returns
    -------
    dict
        Response from PID update request.

    """
    if not url:
        raise HTTPException(
            status_code=500,
            detail="PID service URL not configured in environment variables",
        )

    # Wrap input data using common function
    wrapped_data = wrap_pid_data(data)

    # Construct full URL with handle suffix
    full_url = f"{url}/{handle_suffix}"

    # Create base64 encoded auth header
    import base64

    auth_string = f"{settings.PID_USERNAME}:{settings.PID_PASSWORD}"
    auth_bytes = auth_string.encode("ascii")
    base64_auth = base64.b64encode(auth_bytes).decode("ascii")
    headers = {"Authorization": f"Basic {base64_auth}"}

    # Make PUT request to PID service with auth headers
    async with httpx.AsyncClient() as client:
        response = await client.put(
            full_url, json=wrapped_data, headers=headers
        )
        return response.json()
