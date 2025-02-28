from typing import Optional, List
from fastapi import HTTPException
from pydantic import BaseModel
from fastapi import APIRouter
from efi_api.core.elasticsearch import es_client  
from efi_api.core.config import settings
import logging
router = APIRouter()

logger = logging.getLogger(__name__)

@router.post(
    "/getWorkByID/{id}",
    summary="Get manifest by work ID",
    tags=["Frontend"]
)
async def get_work_by_id(id: str):
    try:
        result_manifest = es_client.search(
            index=settings.ES_INDEX,
            body={
                "query": {
                    "term": {
                        "_id": id
                    }
                }
            }
        )
        return result_manifest["hits"]["hits"]

    except Exception as e:
        logger.error(f"Error getting manifest for work {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

