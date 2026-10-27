from datetime import UTC, datetime
import logging
from typing import Annotated
from urllib import parse
import uuid

from authlib.integrations.base_client.errors import (
    MismatchingStateError,
    OAuthError,
)
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_csrf_protect import CsrfProtect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_502_BAD_GATEWAY,
)

from ..core.config import settings
from ..core.db import get_db
from ..helpers.auth import (
    build_session_info,
    classify,
    derive_access_expiry,
    revoke_provider_token,
)
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


async def _refresh_session_tokens(session, store: SessionStore) -> None:
    """Perform a refresh-token grant against the identity provider.

    Raises if the provider rejects the refresh or the request otherwise fails.
    Token values are never logged.
    """
    new_token = await oauth.academiccloud.fetch_access_token(
        grant_type="refresh_token",
        refresh_token=session.refresh_token,
    )
    await store.update_tokens(session, new_token)


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

    if classify(store.to_dict(session)) == "active":
        return build_session_info(store.to_dict(session))

    # The access token can expire while the refresh token remains valid. Keep
    # the server-side session so the client can rotate the tokens via POST
    # /auth/refresh.
    return SessionInfo(
        authenticated=False,
        server_time=int(datetime.now(UTC).timestamp()),
    )


@router.post(
    "/refresh",
    summary="Refresh user session on activity",
    description="""
    Perform refresh-token rotation against the identity provider and return
    the updated session information. This runs regardless of whether the
    current access token has expired. Requires valid CSRF token.
    """,
    dependencies=[Depends(verify_csrf)],
)
async def refresh(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionInfo:
    """Rotate tokens against the identity provider."""
    sid = request.session.get("sid")
    if not sid:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Not logged in"
        )

    store = SessionStore(db)
    session = await store.get(sid)
    if not session or not session.refresh_token:
        if session:
            await store.delete(session)
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Not logged in"
        )

    try:
        await _refresh_session_tokens(session, store)
    except Exception as e:
        log.error(f"Token refresh failed: {e}")
        await store.delete(session)
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Not logged in"
        ) from None

    return build_session_info(store.to_dict(session))


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
            await _revoke_session_tokens(session)
            await store.delete(session)

    request.session.pop("sid", None)
    return Response(status_code=204)


async def _revoke_session_tokens(session) -> None:
    """Best-effort provider token revocation on signout.

    Revocation failures must not prevent local logout, so they are logged and
    swallowed here.
    """
    if not settings.AC_CLIENT_ID and not settings.AC_SECRET_KEY:
        return
    try:
        metadata = await oauth.academiccloud.load_server_metadata()
    except Exception as e:
        log.warning(f"Could not load provider metadata during signout: {e}")
        return
    try:
        await revoke_provider_token(
            client_id=settings.AC_CLIENT_ID,
            client_secret=settings.AC_SECRET_KEY,
            metadata=metadata,
            refresh_token=session.refresh_token,
            access_token=session.access_token,
        )
    except Exception as e:
        log.warning(f"Token revocation failed during signout: {e}")


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
async def signin_ac_get(request: Request):
    return await redirect_to_ac(request)


async def redirect_to_ac(request: Request):
    if not settings.AC_CLIENT_ID:
        log.error("OAuth client id is not configured")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth client is not configured",
        )

    redirect_uri = request.url_for("auth")
    proxy_host = request.headers.get("x-forwarded-host")
    if proxy_host:
        scheme = request.headers.get("x-forwarded-proto")
        if scheme not in ("http", "https"):
            log.warning(
                f"Rejecting signin with invalid forwarded proto: {scheme}"
            )
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="Invalid forwarded protocol",
            )
        redirect_uri = parse.urljoin(
            f"{scheme}://{proxy_host}",
            redirect_uri.path,
        )
    log.debug(f"Passing as callback: {redirect_uri}")
    try:
        return await oauth.academiccloud.authorize_redirect(
            request, redirect_uri
        )
    except OAuthError as e:
        log.error(f"OAuth authorization initiation failed: {e}")
        raise HTTPException(
            status_code=HTTP_502_BAD_GATEWAY,
            detail="Could not initiate authentication",
        ) from e
    except Exception as e:
        log.error(f"Authorization initiation failed: {e}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not initiate authentication",
        ) from e


@router.get("/callback/academiccloud")
async def auth(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    params = request.query_params

    error = params.get("error")
    if error:
        log.warning(f"Identity provider returned an error: {error}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Authentication failed",
        )

    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        log.warning("OAuth callback missing code or state parameter")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Missing OAuth parameters",
        )

    try:
        token = await oauth.academiccloud.authorize_access_token(request)
    except MismatchingStateError as e:
        log.warning("OAuth state mismatch during callback")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state",
        ) from e
    except OAuthError as e:
        log.warning(f"OAuth callback token exchange failed: {e}")
        raise HTTPException(
            status_code=HTTP_400_BAD_REQUEST,
            detail="Authentication failed",
        ) from e

    userinfo = token.get("userinfo")
    access_token = token.get("access_token")
    expires_at = token.get("expires_at")
    if not userinfo or not access_token or not expires_at:
        log.error("Identity provider returned an incomplete token response")
        raise HTTPException(
            status_code=HTTP_502_BAD_GATEWAY,
            detail="Invalid response from identity provider",
        )

    aud = userinfo.get("aud")
    if not aud:
        log.error("Identity provider userinfo is missing audience")
        raise HTTPException(
            status_code=HTTP_502_BAD_GATEWAY,
            detail="Invalid response from identity provider",
        )

    scopes = token.get("scope", "").split()
    user = dict(
        name=userinfo.get("name"),
        email=userinfo.get("email"),
        uid=userinfo.get("uid"),
        orgid=userinfo.get("ou"),
    )
    if not user["name"] or not user["email"] or not user["uid"]:
        log.error("Identity provider userinfo is missing required fields")
        raise HTTPException(
            status_code=HTTP_502_BAD_GATEWAY,
            detail="Invalid response from identity provider",
        )

    try:
        access_expires_at = derive_access_expiry(token)
    except Exception as e:
        log.error(f"Invalid token expiry from identity provider: {e}")
        raise HTTPException(
            status_code=HTTP_502_BAD_GATEWAY,
            detail="Invalid response from identity provider",
        ) from e

    sid = str(uuid.uuid4())
    request.session["sid"] = sid

    await SessionStore(db).create(
        sid=sid,
        user_name=user["name"],
        user_email=user["email"],
        user_uid=user["uid"],
        user_orgid=user.get("orgid"),
        audience=aud,
        scopes=scopes,
        access_token=access_token,
        refresh_token=token.get("refresh_token"),
        id_token=token.get("id_token", ""),
        access_expires_at=int(access_expires_at.timestamp()),
    )

    return RedirectResponse(url=FRONTEND_CALLBACK)
