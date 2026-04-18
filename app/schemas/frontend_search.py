from pydantic import BaseModel, ConfigDict, Field


class SearchParams(BaseModel):
    model_config = ConfigDict(serialize_by_alias=True)

    query: str = Field(
        default="",
        description="Search query string to match against titles and content",
        examples=["test"],
    )
    facetFilters: list[list[str] | str] | None = Field(
        default=None,
        description="Nested list of facet filters in format ['field:value']."
        " Inner lists are OR'ed, outer lists are AND'ed",
        examples=[
            ["production:Hermann Schlenker Filmproduktion"],
            ["years:1977"],
        ],
    )
    facets: list[str] | str | None = Field(
        default=None,
        description="List of facet fields to aggregate results by,"
        " or single facet field",
        examples=[
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
        ],
    )
    numericRefinements: dict[str, dict[str, int]] | None = Field(
        default=None,
        alias="numeric-refinements",
        description="Custom workaround for a range facet",
        examples=[{"production_in_year": {">=": 1956, "<=": 1965}}],
    )
    highlightPreTag: str | None = Field(
        default="__ais-highlight__",
        description="Opening HTML tag for highlighting matched terms",
        examples=["__ais-highlight__"],
    )
    highlightPostTag: str | None = Field(
        default="__/ais-highlight__",
        description="Closing HTML tag for highlighting matched terms",
        examples=["__/ais-highlight__"],
    )
    hitsPerPage: int | None = Field(
        default=20,
        description="Number of results to return per page",
        ge=0,
        le=100,
        examples=[20],
    )
    maxValuesPerFacet: int | None = Field(
        default=10,
        description="Maximum number of values to return for each facet",
        ge=1,
        le=100,
        examples=[10],
    )
    page: int | None = Field(
        default=0,
        description="Zero-based page number for pagination",
        ge=0,
        examples=[0],
    )
    analytics: bool | None = Field(
        default=True, description="Whether to enable analytics"
    )
    clickAnalytics: bool | None = Field(
        default=True, description="Whether to enable click analytics"
    )


class SearchRequest(BaseModel):
    indexName: str = Field(
        description="Name of the search index to query",
        examples=["21.11155-denormalised-work"],
    )
    params: SearchParams


class Exhaustive(BaseModel):
    facetsCount: bool
    nbHits: bool
    typo: bool


class FacetOrder(BaseModel):
    order: list


class FacetOrdering(BaseModel):
    facets: FacetOrder
    values: dict[str, dict[str, str]]


class RenderingContent(BaseModel):
    facetOrdering: FacetOrdering


class SearchResult(BaseModel):
    appliedRules: list
    exhaustive: Exhaustive
    hitsPerPage: int
    processingTimeMS: int
    nbHits: int
    nbWorks: int | None = Field(
        default=None,
        description="Number of works matching the query",
        examples=[1],
    )
    nbManifestations: int | None = Field(
        default=None,
        description="Number of manifestations matching the query",
        examples=[2],
    )
    nbItems: int | None = Field(
        default=None,
        description="Number of items matching the query",
        examples=[2],
    )
    page: int
    nbPages: int
    query: str
    renderingContent: RenderingContent
    facets: dict[str, dict[str | int, int]]
    facets_stats: dict
    hits: list[dict]
    index: str
    params: str


class SearchResponse(BaseModel):
    results: list[SearchResult] = Field(
        description="List of search results containing hits, facets,"
        " pagination and other metadata"
    )
