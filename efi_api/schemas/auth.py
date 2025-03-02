from pydantic import BaseModel, Field
from datetime import datetime, timedelta


class User(BaseModel):
    name: str
    email: str
    uid: str
    orgid: str


class Token(BaseModel):
    user: User
    audience: str
    scopes: list[str]
    timestamp: int
    timeout: int
