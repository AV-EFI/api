from pydantic import BaseModel


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


class CsrfToken(BaseModel):
    csrfToken: str
