from fastapi import APIRouter, HTTPException, status
from ..schemas.efi_schema import EFIRequest, EFIResponse, ErrorResponse

router = APIRouter()

@router.post("/efi", 
            response_model=EFIResponse,
            response_model_exclude_unset=True,
            status_code=status.HTTP_201_CREATED,
            summary="Process EFI data",
            description="Endpoint to process EFI (Extended Film Information) data. "
                        "It accepts a JSON payload containing film metadata and returns "
                        "a processed version of the same data.",
            response_description="Processed EFI data with a success message",
            responses={
                400: {"model": ErrorResponse, "description": "Bad Request"},
                500: {"model": ErrorResponse, "description": "Internal Server Error"}
            })

async def process_efi(request: EFIRequest):
    """
    Process the incoming EFI data.
    
    - **request**: A JSON object containing film metadata
    
    Returns:
    - **message**: A success message
    - **data**: The processed EFI data
    
    Raises:
    - **HTTPException**: 400 Bad Request if the data is invalid
    - **HTTPException**: 500 Internal Server Error for unexpected errors
    """
    try:
        # Process the incoming EFI data
        # For now, we'll just return the same data
        return EFIResponse(
            message="EFI data processed successfully",
            data=request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred")
