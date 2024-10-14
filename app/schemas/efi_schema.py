from pydantic import BaseModel, Field
from typing import List, Optional

class Agent(BaseModel):
    category: str = Field(..., description="Category of the agent")
    has_name: str = Field(..., description="Name of the agent")
    type: str = Field(..., description="Type of the agent (e.g., Person)")
    same_as: Optional[List[dict]] = Field(None, description="References to the same agent in other databases")

class Activity(BaseModel):
    category: str = Field(..., description="Category of the activity")
    has_agent: List[Agent] = Field(..., description="List of agents involved in the activity")
    type: str = Field(..., description="Type of the activity (e.g., CastMember, Writer)")

class Event(BaseModel):
    category: str = Field(..., description="Category of the event")
    has_activity: List[Activity] = Field(..., description="List of activities associated with the event")
    has_date: str = Field(..., description="Date or date range of the event")
    located_in: List[dict] = Field(..., description="Location information for the event")

class EFIRequest(BaseModel):
    category: str = Field(..., description="Category of the film variant")
    has_primary_title: dict = Field(..., description="Primary title information")
    described_by: dict = Field(..., description="Information about the entity describing the film")
    has_event: List[Event] = Field(..., description="List of events associated with the film")
    has_identifier: List[dict] = Field(..., description="List of identifiers for the film")
    type: str = Field(..., description="Type of the film (e.g., Monographic)")
    has_genre: List[dict] = Field(..., description="List of genres associated with the film")
    same_as: List[dict] = Field(..., description="References to the same film in other databases")

class EFIResponse(BaseModel):
    message: str = Field(..., description="A message indicating the result of the operation")
    data: EFIRequest = Field(..., description="The processed EFI data")
    
class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error details")