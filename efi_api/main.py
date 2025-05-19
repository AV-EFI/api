import logging
import os
from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .core.config import settings
from .routers import auth, efi, health, hello, search, transform, user
from .routers.frontend import frontend_search, view
from .routers.pid import create,update, pid

ROOT_PATH = "/api/v1"

tags_metadata = [
    {
        'name': 'hello',
        'description': 'Say hello to the world!'
    }
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
    docs_url=f"{ROOT_PATH}/docs",
    redoc_url=f"{ROOT_PATH}/redoc",
    openapi_url=f"{ROOT_PATH}/openapi.json",
    openapi_tags=tags_metadata,
)
app.add_middleware(
    SessionMiddleware, secret_key=settings.SESSION_SECRET,
    same_site='lax', https_only=True, max_age=16 * 60 * 60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix=ROOT_PATH)

api.include_router(hello.router, prefix='/hello', tags=['hello'])
api.include_router(health.router, tags=["Health"])
api.include_router(user.router, prefix="/user", tags=["User"])
api.include_router(efi.router, tags=["EFI"])
api.include_router(create.router, prefix="/pid", tags=["PID"])
api.include_router(update.router, prefix="/pid", tags=["PID"])
api.include_router(pid.router, prefix="", tags=["PID"])
api.include_router(frontend_search.router, prefix="/frontend", tags=["Frontend"])
api.include_router(view.router, prefix="/frontend", tags=["Frontend"])
api.include_router(search.router, prefix="", tags=["Search"])
api.include_router(transform.router, prefix="", tags=["Transform"])

app.include_router(api)
app.include_router(auth.router, prefix="/auth", tags=["Auth"])

if __name__ == '__main__':
    uvicorn.run("efi_api.main:app", host='0.0.0.0', port=8000)
