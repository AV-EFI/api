import logging

from fastapi import APIRouter

from ...helpers.frontend_search import process_search_request
from ...schemas.frontend_search import SearchRequest, SearchResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.options(
    "/search",
    summary="Search content options",
    tags=["Frontend"],
    include_in_schema=False  # Hide from API docs since it's just for CORS
)
async def search_options():
    return {"message": "OK"}

@router.post(
    "/search",
    summary="Search content using Elasticsearch",
    description="""
    Performs a multi-faceted search across the content index with support for:
    - Full-text search with boosted title matches
    - Faceted filtering and aggregations
    - Result highlighting
    - Pagination

    Multiple search requests can be submitted at once.
    """,
    tags=["Frontend"],
)
async def multi_search(search_requests: list[SearchRequest]) -> SearchResponse:
    results = []
    for request in search_requests:
        results.append(process_search_request(request))
    return {"results": results}
