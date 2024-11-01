from fastapi import APIRouter, HTTPException
from app.core.elasticsearch import es_client

router = APIRouter()

@router.get("/health", summary="Health Check", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify Elasticsearch connection
    
    Returns:
        dict: Status of the application and Elasticsearch connection
    
    Raises:
        HTTPException: If Elasticsearch connection fails
    """
    try:
        if es_client.ping():
            return {
                "status": "healthy",
                "elasticsearch": "connected"
            }
        return {
            "status": "unhealthy",
            "elasticsearch": "not connected"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service Unavailable: {str(e)}"
        )