from datetime import datetime
import logging
from urllib import parse

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Header, HTTPException
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


@router.get('/academiccloud/login')
async def login(request: Request):
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
