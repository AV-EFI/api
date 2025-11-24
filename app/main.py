import logging
import os
from pathlib import Path

import elasticsearch
import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .core.config import settings
from .routers import auth, health, matches
from .routers.frontend import frontend_search, view
# from .routers.pid import create,update, pid

EFI_ROOT = "/rest"
EFI_PATH = f"{EFI_ROOT}/v1"

tags_metadata = [
    {
        'name': 'Search',
        'description': 'Search the database.',
    },
    {
        'name': 'Frontend',
        'description': 'Internal endpoints for AVefi frontend.',
    },
]

loglevel = os.environ.get(
    f"{__package__.upper()}_LOGLEVEL", 'WARNING').upper()
num_level = getattr(logging, loglevel, None)
if not isinstance(num_level, int):
    raise ValueError(f"Invalid log level: {loglevel}")
logging.basicConfig(
    level=num_level, format='%(levelname)s:%(name)s: %(message)s')

# Read version from the VERSION file
path_to_app = Path(__file__).parent
path_to_version = Path(path_to_app, 'VERSION').resolve()
with open(path_to_version, 'r') as f:
    version = f.read()

app = FastAPI(
    title='AV-EFI API',
    description='This is the backend for the AV-EFI project.',
    version=version,
    docs_url=f"{EFI_ROOT}/docs",
    redoc_url=f"{EFI_ROOT}/redoc",
    openapi_url=f"{EFI_ROOT}/openapi.json",
    tags_metadata=[
        {
            'name': 'Auth',
            'description': 'Authenticate with OpenID Connect.',
        },
    ],
)
app.add_middleware(
    SessionMiddleware, secret_key=settings.SESSION_SECRET,
    same_site='lax', https_only=True, max_age=16 * 60 * 60)

api = FastAPI(
    title='AV-EFI API',
    description='This is the backend for the AV-EFI project.',
    version=version,
    openapi_tags=tags_metadata,
)

@api.exception_handler(elasticsearch.NotFoundError)
async def elastic_404_handler(
        request: Request, exc: elasticsearch.NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content="Not Found")

api.include_router(health.router, tags=["Health"])
# api.include_router(create.router, prefix="/pid", tags=["PID"])
# api.include_router(update.router, prefix="/pid", tags=["PID"])
# api.include_router(pid.router, prefix="", tags=["PID"])
api.include_router(frontend_search.router, prefix="/frontend", tags=["Frontend", "Search"])
api.include_router(view.router, prefix="/frontend", tags=["Frontend"])
api.include_router(matches.router, prefix="", tags=["Matching", "Search"])
# api.include_router(transform.router, prefix="", tags=["Transform"])

app.mount(EFI_PATH, api)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])

if __name__ == '__main__':
    uvicorn.run("app.main:app", host='0.0.0.0', port=8000)
