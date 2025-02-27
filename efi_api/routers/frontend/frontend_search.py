from http.client import HTTPException
from fastapi import APIRouter
import logging
from typing import List

from efi_api.core.config import settings
from efi_api.schemas.frontend_search import SearchRequest, SearchResponse
from efi_api.helpers.frontend_search_v2 import build_es_query, execute_search, transform_facets, transform_hits

router = APIRouter()
url = settings.PID_SERVICE_URL

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@router.options(
    "/frontend/v2/search",
    summary="Search content options",
    tags=["Frontend"],
    include_in_schema=False  # Hide from API docs since it's just for CORS
)
async def search_options():
    return {"message": "OK"} 

@router.post(
    "/frontend/search",
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
async def multi_search(search_requests: List[SearchRequest]):
    try:
        # For now, we'll just handle the first request in the array
        search_request = search_requests[0]
        
        # logger.debug(f"Search request: {search_request.params}")
        es_query = build_es_query(search_request.params)
        # logger.debug(f"Elasticsearch query: {es_query}")
        
        response = execute_search(es_query)
        # logger.debug(f"Elasticsearch response: {response}")

        hits = transform_hits(response["hits"]["hits"], search_request.params.query)
        total_hits = response["hits"]["total"]["value"]
        facets = transform_facets(response["aggregations"])
        
        # Wrap the response in a results array
        return {
            "results": [{
                "hits": hits,
                "facets": facets,
                "page": search_request.params.page,
                "nbPages": (total_hits + search_request.params.hitsPerPage - 1) // search_request.params.hitsPerPage,
                "nbHits": total_hits,
                "appliedRules": [],
                "exhaustiveNbHits": True,
                "exhaustiveFacetsCount": True,
                "exhaustiveTypo": True,
                "exhaustive": {
                    "facetsCount": True,
                    "nbHits": True,
                    "typo": True
                },
                "hitsPerPage": search_request.params.hitsPerPage,
                "processingTimeMS": 18,
                "query": search_request.params.query,
                "renderingContent": {
                    "facetOrdering": {
                        "facets": {
                            "order": [
                                "has_sound_type",
                                "in_language_code",
                                "has_genre_has_name",
                                "subjects",
                                "directors_or_editors",
                                "castmembers",
                                "production",
                                "years",
                                "located_in_has_name",
                                "has_duration_has_value",
                                "has_issuer_name",
                                "has_format_type",
                                "manifestation_event_type",
                                "has_issuer_name",
                                "has_colour_type",
                                "item_element_type",
                                "has_form"
                            ]
                        },
                        "values": {
                            "has_sound_type": {"sortRemainingBy": "count"},
                            "in_language_code": {"sortRemainingBy": "count"},
                            "has_genre_has_name": {"sortRemainingBy": "count"},
                            "subjects": {"sortRemainingBy": "count"},
                            "directors_or_editors": {"sortRemainingBy": "count"},
                            "castmembers": {"sortRemainingBy": "count"},
                            "production": {"sortRemainingBy": "count"},
                            "years": {"sortRemainingBy": "count"},
                            "located_in_has_name": {"sortRemainingBy": "count"},
                            "has_duration_has_value": {"sortRemainingBy": "count"},
                            "has_issuer_name": {"sortRemainingBy": "count"},
                            "has_format_type": {"sortRemainingBy": "count"},
                            "manifestation_event_type": {"sortRemainingBy": "count"},
                            "has_colour_type": {"sortRemainingBy": "count"},
                            "item_element_type": {"sortRemainingBy": "count"},
                            "has_form": {"sortRemainingBy": "count"}
                        }
                    }
                }
            }]
        }
    
    except Exception as e:
        logger.error(f"Unexpected error during search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
