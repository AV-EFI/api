from fastapi import APIRouter

from ..helpers import matching
from ..schemas.efi_schema import efi
from ..schemas.elastic_schema import SearchResponse

router = APIRouter()

@router.post("/matches", response_model=SearchResponse)
async def find_matching_works(request: efi.WorkVariant):
    """
    Search for matching works based on title, date, director, country.

    Returns matching works and scores.
    """
    return matching.get_works_matching(request)
