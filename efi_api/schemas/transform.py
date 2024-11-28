from pydantic import BaseModel
from typing import List, Any

class Title(BaseModel):
    has_name: str
    type: str
    has_ordering_name: str

class Agent(BaseModel):
    category: str
    has_name: str
    type: str

class Activity(BaseModel):
    category: str
    has_agent: List[Agent]
    type: str

class Location(BaseModel):
    category: str
    has_name: str

class Event(BaseModel):
    category: str
    has_activity: List[Activity]
    has_date: str
    located_in: List[Location]

class InputData(BaseModel):
    category: str
    has_primary_title: Title
    has_event: List[Event]
    type: str

# Output models
class TransformedRecord(BaseModel):
    type: str
    parsed_data: Any
    idx: int