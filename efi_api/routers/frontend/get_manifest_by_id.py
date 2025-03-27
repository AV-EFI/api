from typing import Optional, List
from fastapi import HTTPException
from pydantic import BaseModel
from fastapi import APIRouter
from efi_api.core.elasticsearch import es_client  
from efi_api.core.config import settings
import logging
router = APIRouter()

logger = logging.getLogger(__name__)

async def get_items_by_manifest_id(manifest_id: str):
    try:
        result_items = es_client.search(
            index=settings.ES_INDEX,
            body={
                "query": {
                    "bool": {
                        "must": {
                            "match": {
                                "has_record.is_item_of.id.keyword": manifest_id
                            }
                        }
                    }
                }
            }
        )
        return result_items["hits"]["hits"] if result_items["hits"]["hits"] else None
    except Exception as e:
        logger.error(f"Error getting items for manifest {manifest_id}: {str(e)}", exc_info=True)
        return None
    
@router.post(
    "/get_manifest_by_id/{id}",
    summary="Get manifest by ID",
    tags=["Frontend"]
)
async def get_manifest_by_id(id: str):
    try:
        result_manifest = es_client.search(
            index=settings.ES_INDEX,
            body={
                "query": {
                    "bool": {
                        "must": {
                            "match": {
                                "has_record.is_manifestation_of.id.keyword": "21.11155/"+id
                            }
                        }
                    }
                }
            }
        )
        
        # Fetch items for each manifest
        for manifest in result_manifest["hits"]["hits"]:
            if manifest.get("_source", {}).get("handle"):
                items = await get_items_by_manifest_id(manifest["_source"]["handle"])
                manifest["_source"]["items"] = items

        return result_manifest["hits"]["hits"]

    except Exception as e:
        logger.error(f"Error getting manifest for work {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
