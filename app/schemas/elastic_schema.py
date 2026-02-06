from pydantic import BaseModel, Field


class TotalHits(BaseModel):
    value: int = Field(description="Number of total hits.")
    relation: str = Field(
        description="Indicator whether `value` is an exact number or a lower"
        " bound."
    )


class SearchResponse(BaseModel):
    total: TotalHits
    hits: list[dict] = Field(description="List of resutls.")
    max_score: float = Field(description="Maximum score amongst hits.")
