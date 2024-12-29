from http.client import HTTPException
from fastapi import APIRouter
import logging

from efi_api.core.config import settings
from efi_api.schemas.frontend_search_v2 import SearchRequest, SearchResponse
from efi_api.helpers.frontend_search_v2 import build_es_query, execute_search, transform_facets, transform_hits

router = APIRouter()
url = settings.PID_SERVICE_URL

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@router.post(
    "/frontend/v2/search",
    summary="Search content using Elasticsearch",
    description="""
    Performs a multi-faceted search across the content index with support for:
    - Full-text search with boosted title matches
    - Faceted filtering and aggregations
    - Result highlighting
    - Pagination
    
    The search query matches against both titles (boosted) and all text fields with fuzzy matching enabled.
    Results can be filtered using facets, and facet counts are returned for refinement.
    """,
    response_model=SearchResponse,
    tags=["Frontend"],
)
@router.post("/frontend/v2/search", summary="Elastic Search", tags=["Frontend"])
async def multi_search(search_request: SearchRequest):
    try:
        es_query = build_es_query(search_request)
        logger.debug(f"Elasticsearch query: {es_query}")
        
        response = execute_search(es_query)
        logger.debug(f"Elasticsearch response: {response}")

        hits = transform_hits(response["hits"]["hits"])
        total_hits = response["hits"]["total"]["value"]
        facets = transform_facets(response["aggregations"])

        return {
            "hits": hits,
            "facets": facets,
            "page": search_request.page,
            "nbPages": (total_hits + search_request.hitsPerPage - 1) // search_request.hitsPerPage,
            "nbHits": total_hits
        }
    
    except Exception as e:
        logger.error(f"Unexpected error during search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
