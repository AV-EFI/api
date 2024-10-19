from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class SearchRequest(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    director: Optional[str] = None

class SearchResponse(BaseModel):
    matches_found: int
    similar_works: List[Dict]
    # matching_criteria: Dict[str, bool]