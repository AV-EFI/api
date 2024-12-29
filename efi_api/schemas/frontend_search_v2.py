from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class SearchRequest(BaseModel):
    query: str = Field(
        description="Search query string to match against titles and content",
        example="DIE HEIMAT DES DON QUIJOTE"
    )
    facetFilters: Optional[List[List[str]]] = Field(
        default=None,
        description="Nested list of facet filters in format ['field:value']. Inner lists are OR'ed, outer lists are AND'ed",
        example=[["countries:Frankreich"]]
    )
    facets: Optional[List[str]] = Field(
        default=None,
        description="List of facet fields to aggregate results by",
        example=["castmembers", "categories", "category_clean", "countries", "directors", "producers", "productionyears", "subjects"]
    )
    highlightPreTag: Optional[str] = Field(
        default="__ais-highlight__",
        description="Opening HTML tag for highlighting matched terms",
        example="__ais-highlight__"
    )
    highlightPostTag: Optional[str] = Field(
        default="__/ais-highlight__",
        description="Closing HTML tag for highlighting matched terms",
        example="__/ais-highlight__"
    )
    hitsPerPage: Optional[int] = Field(
        default=20,
        description="Number of results to return per page",
        ge=1,
        le=100,
        example=20
    )
    maxValuesPerFacet: Optional[int] = Field(
        default=10,
        description="Maximum number of values to return for each facet",
        ge=1,
        le=100,
        example=10
    )
    page: Optional[int] = Field(
        default=0,
        description="Zero-based page number for pagination",
        ge=0,
        example=0
    )

class SearchResponse(BaseModel):
    hits: List[dict] = Field(
        description="List of search results with metadata and highlighting"
    )
    facets: dict = Field(
        description="Aggregated facet values and their counts"
    )
    page: int = Field(
        description="Current page number"
    )
    nbPages: int = Field(
        description="Total number of pages available"
    )
    nbHits: int = Field(
        description="Total number of matching documents"
    )

