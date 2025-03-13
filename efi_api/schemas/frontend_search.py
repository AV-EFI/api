from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union, Any


class SearchParams(BaseModel):
    query: str = Field(
        description="Search query string to match against titles and content",
        example="test"
    )
    facetFilters: Optional[List[List[str]]] = Field(
        default=None,
        description="Nested list of facet filters in format ['field:value']. Inner lists are OR'ed, outer lists are AND'ed",
        example=[
            ["production:Hermann Schlenker Filmproduktion"],
            ["years:1977"]
        ]
    )
    facets: Optional[Union[List[str], str]] = Field(
        default=None,
        description="List of facet fields to aggregate results by, or single facet field",
        example=[
            "castmembers",
            "directors_or_editors",
            "has_colour_type",
            "has_duration_has_value",
            "has_form",
            "has_format_type",
            "has_genre_has_name",
            "has_issuer_name",
            "has_sound_type",
            "in_language_code",
            "item_element_type",
            "located_in_has_name",
            "manifestation_event_type",
            "production",
            "subjects",
            "years"
        ]
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
        ge=0,
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
    analytics: Optional[bool] = Field(
        default=True,
        description="Whether to enable analytics"
    )
    clickAnalytics: Optional[bool] = Field(
        default=True,
        description="Whether to enable click analytics"
    )

class SearchRequest(BaseModel):
    indexName: str = Field(
        description="Name of the search index to query",
        example="21.11155-denormalised-work"
    )
    params: SearchParams

class SearchResponse(BaseModel):
    results: List[dict] = Field(
        description="List of search results containing hits, facets, pagination and other metadata"
    )

