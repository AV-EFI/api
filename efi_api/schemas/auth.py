from pydantic import BaseModel, Field
from datetime import datetime, timedelta

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_at: datetime

class UserCredentials(BaseModel):
    username: str
    password: str