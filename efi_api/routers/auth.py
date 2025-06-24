from datetime import datetime
import logging
from urllib import parse

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi_csrf_protect import CsrfProtect
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from ..core.config import settings
from ..helpers.auth import SESSION_TIMEOUT, valid_access_token
from ..helpers.mock_auth import mock_pid_system_auth,create_access_token
from ..schemas.auth import CsrfToken, Token, User


log = logging.getLogger(__name__)
router = APIRouter()
FRONTEND_CALLBACK = '/'


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
    # response_model=Token,
    # responses={
    #     status.HTTP_401_UNAUTHORIZED: {"description": "Not logged in"},
    # }
)
async def session(request: Request):
    try:
        return valid_access_token(request)
    except:
        return {}


@router.get(
    '/signout',
    summary="Log user out",
    description="""Invalidate session, hence requiring reauthentication
      for privileged access.""",
    response_description="""Redirect to root of the frontend app.""",
)
async def signout(request: Request):
    request.session.pop('token', None)
    return RedirectResponse(url='/')


@router.get("/csrf")
async def csrf_token(
        request: Request, csrf_protect: CsrfProtect = Depends()) -> CsrfToken:
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = JSONResponse(status_code=200, content={"csrfToken": csrf_token})
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


oauth = OAuth()
oauth.register(
    'academiccloud',
    client_id=settings.AC_CLIENT_ID,
    client_secret=settings.AC_SECRET_KEY,
    server_metadata_url=settings.AC_METADATA_URL,
    client_kwargs={
        'scope': 'openid email profile',
        'code_challenge_method': "S256",
    }
)


@router.post(
    '/signin/keycloak',
    summary="Authenticate user via Academiccloud.",
    description="""Authenticate user via external identity provider.""",
    response_description="""Redirect to external identity provider and
      hand back control to the frontend eventually.""",
)
async def signin_ac(
        request: Request,
        csrf_protect: CsrfProtect = Depends()):
    await csrf_protect.validate_csrf(request)
    return await redirect_to_ac(request)


@router.get(
    '/signin/keycloak',
    summary="Authenticate user via Academiccloud.",
    description="""Authenticate user via external identity provider.""",
    response_description="""Redirect to external identity provider and
      hand back control to the frontend eventually.""",
)
async def signin_ac(request: Request):
    return await redirect_to_ac(request)


async def redirect_to_ac(request: Request):
    redirect_uri = request.url_for('auth')
    proxy_host = request.headers.get('x-forwarded-host')
    if proxy_host:
        redirect_uri = parse.urljoin(
            f"{request.headers.get('x-forwarded-proto')}://{proxy_host}",
            redirect_uri.path)
    log.debug(f"Passing as callback: {redirect_uri}")
    return await oauth.academiccloud.authorize_redirect(request, redirect_uri)


@router.get('/academiccloud/auth')
async def auth(request: Request):
    token = await oauth.academiccloud.authorize_access_token(request)
    userinfo = token.get('userinfo')
    if userinfo:
        current_time = int(datetime.utcnow().timestamp())
        scopes = token['scope'].split()
        user = dict(
            name=userinfo['name'],
            email=userinfo['email'],
            uid=userinfo['uid'],
            orgid=userinfo['ou'],
        )
        request.session['token'] = dict(
            user=user,
            audience=userinfo['aud'],
            scopes=scopes,
            timestamp=current_time,
            timeout=SESSION_TIMEOUT,
        )
    return RedirectResponse(url=FRONTEND_CALLBACK)
