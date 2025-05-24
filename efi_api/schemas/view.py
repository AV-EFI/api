from pydantic import BaseModel, Field


class DetailView(BaseModel):
    handle: str = Field(description="Identifies object of interest.")
    compound_record: dict = Field(
        description="Record providing complete context for detail view.")
