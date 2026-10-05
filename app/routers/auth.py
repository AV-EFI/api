from datetime import UTC, datetime
import logging
from typing import Annotated
from urllib import parse
import uuid

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_csrf_protect import CsrfProtect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse
from starlette.status import HTTP_401_UNAUTHORIZED

from ..core.config import settings
from ..core.db import get_db
from ..helpers.auth import build_session_info, classify, derive_expiries
from ..helpers.session_store import SessionStore
from ..schemas.auth import CsrfToken, SessionInfo

log = logging.getLogger(__name__)
router = APIRouter()
FRONTEND_CALLBACK = "/"

oauth = OAuth()
oauth.register(
    "academiccloud",
    client_id=settings.AC_CLIENT_ID,
    client_secret=settings.AC_SECRET_KEY,
    server_metadata_url=settings.AC_METADATA_URL,
    client_kwargs={
        "scope": "openid email profile org",
        "code_challenge_method": "S256",
    },
)


async def verify_csrf(
    request: Request,
    csrf_protect: Annotated[CsrfProtect, Depends()],
) -> None:
    """Verify CSRF token for state-changing requests."""
    await csrf_protect.validate_csrf(request)


async def get_session_for_refresh(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> tuple[dict | None, SessionStore]:
    """Get session from cookie and refresh if needed. Raises 401 if expired."""
    sid = request.session.get("sid")
    if not sid:
        return None, SessionStore(db)

    store = SessionStore(db)
    session = await store.get(sid)
    if not session:
        return None, store

    state = classify(store.to_dict(session))

    if state == "active":
        return store.to_dict(session), store

    if state == "refreshable":
        try:
            metadata = await oauth.academiccloud.load_server_metadata()
            new_token = await oauth.academiccloud.fetch_access_token(
                url=metadata.get("token_endpoint", "/oauth/token"),
                grant_type="refresh_token",
                refresh_token=session.refresh_token,
            )
            await store.update_tokens(session, new_token)
            return store.to_dict(session), store
        except Exception as e:
            log.error(f"Token refresh failed: {e}")
            await store.delete(session)
            return None, store

    # expired
    await store.delete(session)
    return None, store


@router.get(
    "/session",
    summary="Provide information about current user session",
    description="""
    Provide information about current user session without resetting
    any expiry. This endpoint is read-only and does not extend the
    session lifetime. To keep the session alive on user activity, call
    POST /auth/refresh instead.
    """,
    response_model=SessionInfo,
)
async def session(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
):
    sid = request.session.get("sid")
    if not sid:
        return SessionInfo(
            authenticated=False,
            server_time=int(datetime.now(UTC).timestamp()),
        )

    store = SessionStore(db)
    session = await store.get(sid)
    if not session:
        return SessionInfo(
            authenticated=False,
            server_time=int(datetime.now(UTC).timestamp()),
        )

    state = classify(store.to_dict(session))

    if state == "active" or state == "refreshable":
        return build_session_info(store.to_dict(session))

    # Expired
    await store.delete(session)
    return SessionInfo(
        authenticated=False,
        server_time=int(datetime.now(UTC).timestamp()),
    )


@router.post(
    "/refresh",
    summary="Refresh user session on activity",
    description="""
    Refresh the session token when the user is active. This endpoint
    will use the refresh token to obtain a new access token if the
    current one has expired. Returns the updated session information.
    Requires valid CSRF token.
    """,
    dependencies=[Depends(verify_csrf)],
)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionInfo:
    """Refresh session on user activity."""
    sid = request.session.get("sid")
    if not sid:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Not logged in"
        )

    store = SessionStore(db)
    session = await store.get(sid)
    if not session:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Not logged in"
        )

    state = classify(store.to_dict(session))

    if state == "active":
        return build_session_info(store.to_dict(session))

    if state == "refreshable":
        try:
            metadata = await oauth.academiccloud.load_server_metadata()
            new_token = await oauth.academiccloud.fetch_access_token(
                url=metadata.get("token_endpoint", "/oauth/token"),
                grant_type="refresh_token",
                refresh_token=session.refresh_token,
            )
            await store.update_tokens(session, new_token)
            return build_session_info(store.to_dict(session))
        except Exception as e:
            log.error(f"Token refresh failed: {e}")
            await store.delete(session)
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Not logged in",
            ) from None

    # Expired
    await store.delete(session)
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED, detail="Not logged in"
    )


@router.post(
    "/signout",
    summary="Log user out",
    description="""Invalidate session, hence requiring reauthentication
      for privileged access. Requires valid CSRF token.""",
    response_description="""Returns 204 No Content on success.""",
    dependencies=[Depends(verify_csrf)],
)
async def signout(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
):
    sid = request.session.get("sid")
    if sid:
        store = SessionStore(db)
        session = await store.get(sid)
        if session:
            await store.delete(session)

    request.session.pop("sid", None)
    return Response(status_code=204)


@router.get("/csrf")
async def csrf_token(
    request: Request,
    csrf_protect: Annotated[CsrfProtect, Depends()],
) -> CsrfToken:
    csrf_token, signed_token = csrf_protect.generate_csrf_tokens()
    response = JSONResponse(status_code=200, content={"csrfToken": csrf_token})
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response


@router.get(
    "/signin/academiccloud",
    summary="Initiate authentication via Academiccloud.",
    description="""Initiate authentication via external identity provider
      via redirect. Protected by OAuth state parameter (not CSRF).""",
    response_description="""Redirect to external identity provider.""",
)
@router.get(
    "/signin/academiccloud",
    summary="Authenticate user via Academiccloud.",
    description="""Authenticate user via external identity provider.""",
    response_description="""Redirect to external identity provider and
      hand back control to the frontend eventually.""",
)
async def signin_ac_get(request: Request):
    return await redirect_to_ac(request)


async def redirect_to_ac(request: Request):
    redirect_uri = request.url_for("auth")
    proxy_host = request.headers.get("x-forwarded-host")
    if proxy_host:
        redirect_uri = parse.urljoin(
            f"{request.headers.get('x-forwarded-proto')}://{proxy_host}",
            redirect_uri.path,
        )
    log.debug(f"Passing as callback: {redirect_uri}")
    return await oauth.academiccloud.authorize_redirect(request, redirect_uri)


@router.get("/callback/academiccloud")
async def auth(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    token = await oauth.academiccloud.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if userinfo:
        scopes = token["scope"].split()
        user = dict(
            name=userinfo.get("name"),
            email=userinfo.get("email"),
            uid=userinfo.get("uid"),
            orgid=userinfo.get("ou"),
        )

        access_expires_at, refresh_expires_at = derive_expiries(token)

        sid = str(uuid.uuid4())
        request.session["sid"] = sid

        await SessionStore(db).create(
            sid=sid,
            user_name=user["name"],
            user_email=user["email"],
            user_uid=user["uid"],
            user_orgid=user.get("orgid"),
            audience=userinfo["aud"],
            scopes=scopes,
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            id_token=token.get("id_token", ""),
            access_expires_at=int(access_expires_at.timestamp()),
            refresh_expires_at=(
                int(refresh_expires_at.timestamp())
                if refresh_expires_at
                else None
            ),
        )

    return RedirectResponse(url=FRONTEND_CALLBACK)
