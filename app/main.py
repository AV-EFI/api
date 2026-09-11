import asyncio
from contextlib import asynccontextmanager, suppress
import logging
import os

import elasticsearch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi_csrf_protect.exceptions import CsrfProtectError
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

from . import __version__
from .core.config import settings
from .core.db import engine
from .helpers.auth import delete_expired_sessions
from .routers import auth, health, matches
from .routers.frontend import search, view

# from .routers.pid import create,update, pid

EFI_ROOT = "/rest"
EFI_PATH = f"{EFI_ROOT}/v1"

tags_metadata = [
    {
        "name": "Search",
        "description": "Search the database.",
    },
    {
        "name": "Frontend",
        "description": "Internal endpoints for AVefi frontend.",
    },
]

loglevel = os.environ.get(f"{__package__.upper()}_LOGLEVEL", "WARNING").upper()
num_level = getattr(logging, loglevel, None)
if not isinstance(num_level, int):
    raise ValueError(f"Invalid log level: {loglevel}")
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "uvicorn_default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(message)s",
            "use_colors": None,  # Auto-detect terminal
        },
        "uvicorn_access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": (
                '%(levelprefix)s %(client_addr)s - "%(request_line)s"'
                " %(status_code)s"
            ),
        },
    },
    "handlers": {
        "uvicorn_default": {
            "formatter": "uvicorn_default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "level": loglevel,
        },
        "uvicorn_access": {
            "formatter": "uvicorn_access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "level": loglevel,
        },
    },
    "loggers": {
        "uvicorn": {
            "handlers": ["uvicorn_default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["uvicorn_default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["uvicorn_access"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["uvicorn_default"],
        "level": "DEBUG",
    },
}
logging.config.dictConfig(LOGGING_CONFIG)
log = logging.getLogger(__name__)

api = FastAPI(
    title="AV-EFI API",
    description="This is the backend for the AV-EFI project.",
    version=__version__,
    openapi_tags=tags_metadata,
)


@api.exception_handler(elasticsearch.NotFoundError)
async def elastic_404_handler(
    request: Request, exc: elasticsearch.NotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content="Not Found")


api.include_router(health.router, tags=["Health"])
# api.include_router(create.router, prefix="/pid", tags=["PID"])
# api.include_router(update.router, prefix="/pid", tags=["PID"])
# api.include_router(pid.router, prefix="", tags=["PID"])
api.include_router(
    search.router, prefix="/frontend", tags=["Frontend", "Search"]
)
api.include_router(view.router, prefix="/frontend", tags=["Frontend"])
api.include_router(matches.router, prefix="", tags=["Matching", "Search"])
# api.include_router(transform.router, prefix="", tags=["Transform"])


async def cleanup_sessions_loop():
    """Background task to periodically delete expired sessions."""
    if not settings.SESSION_CLEANUP_ENABLED:
        return

    log.info(
        f"Starting session cleanup loop"
        f" (interval: {settings.SESSION_CLEANUP_INTERVAL}s)"
    )
    from .core.db import get_async_session_maker

    while True:
        try:
            await asyncio.sleep(settings.SESSION_CLEANUP_INTERVAL)
            async with get_async_session_maker() as db:
                deleted = await delete_expired_sessions(db)
                if deleted > 0:
                    log.info(f"Deleted {deleted} expired sessions")
        except asyncio.CancelledError:
            log.info("Session cleanup loop cancelled")
            break
        except Exception as e:
            log.error(f"Session cleanup error: {e}")


cleanup_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    global cleanup_task
    if settings.SESSION_CLEANUP_ENABLED:
        cleanup_task = asyncio.create_task(cleanup_sessions_loop())
    try:
        yield
    finally:
        if cleanup_task:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
        await engine.dispose()


app = FastAPI(
    title="AV-EFI API",
    description="This is the backend for the AV-EFI project.",
    version=__version__,
    docs_url=f"{EFI_ROOT}/docs",
    redoc_url=f"{EFI_ROOT}/redoc",
    openapi_url=f"{EFI_ROOT}/openapi.json",
    tags_metadata=[
        {
            "name": "Auth",
            "description": "Authenticate with OpenID Connect.",
        },
    ],
    lifespan=lifespan,
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    same_site="lax",
    https_only=True,
    max_age=settings.SESSION_COOKIE_MAX_AGE,
)

app.mount(EFI_PATH, api)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])


@app.exception_handler(CsrfProtectError)
async def csrf_error_handler(
    request: Request, exc: CsrfProtectError
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"detail": getattr(exc, "message", "Invalid CSRF token")},
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
