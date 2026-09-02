from pydantic import BaseModel


class User(BaseModel):
    name: str
    email: str
    uid: str
    orgid: str | None = None


class SessionInfo(BaseModel):
    authenticated: bool
    user: User | None = None
    scopes: list[str] = []
    audience: str | None = None
    server_time: int
    expires_at: int | None = None


class CsrfToken(BaseModel):
    csrfToken: str
