from fastapi import APIRouter, Depends, HTTPException, status
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..schemas.auth import Token
from ..helpers.auth import valid_access_token
from .auth import login as login


router = APIRouter()


@router.get(
    '/session',
    summary="Provide information about current user session",
    description="""
    Provide information about current user session. The timestamp
    field indicates current server time (UTC in unix time format) and
    the timeout field (in seconds) indicates how long the session is
    going to be valid. Note that each call to this endpoint resets the
    timestamp to the current time which keeps the session alive for
    another timeout seconds.
    """,
    response_model=Token,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Not logged in"},
    }
)
async def session(request: Request):
    return valid_access_token(request)


@router.get(
    '/login',
    summary="Authenticate user",
    description="""
    Authenticate user via external identity provider.
    """,
    response_description="""
    Redirect to external identity provider and return hand back control
    to the frontend eventually.
    """,
)
async def user_login(request: Request):
    return RedirectResponse(url=request.url_for('login'))


@router.get(
    '/logout',
    summary="Log user out",
    description="""
    Invalidate session, hence requiring reauthentication for privileged
    access.
    """,
    response_description="""
    Redirect to root of the frontend app.
    """,
)
async def user_logout(request: Request):
    request.session.pop('token', None)
    return RedirectResponse(url='/')
