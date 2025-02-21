from pathlib import Path

import uvicorn
from fastapi import APIRouter, FastAPI

from .routers import hello,efi,health,search,transform,auth
from .routers.frontend import frontend_search, frontend_search_v2, get_manifest_by_id, get_work_by_id
from .routers.pid import create,update, pid

ROOT_PATH = "/api/v1"

tags_metadata = [
    {
        'name': 'hello',
        'description': 'Say hello to the world!'
    }
]

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
    openapi_tags=tags_metadata,
)

api = APIRouter(prefix=ROOT_PATH)

api.include_router(hello.router, prefix='/hello', tags=['hello'])
api.include_router(health.router, tags=["Health"])
api.include_router(auth.router, prefix="", tags=["Auth"])
api.include_router(efi.router, prefix="/efi/v1", tags=["EFI"])
api.include_router(create.router, prefix="/efi/pid", tags=["PID"])
api.include_router(update.router, prefix="/efi/pid", tags=["PID"])
api.include_router(pid.router, prefix="", tags=["PID"])
api.include_router(frontend_search.router, prefix="", tags=["Frontend"])
api.include_router(frontend_search_v2.router, prefix="", tags=["Frontend"])
api.include_router(get_manifest_by_id.router, prefix="", tags=["Frontend"])
api.include_router(get_work_by_id.router, prefix="", tags=["Frontend"])
api.include_router(search.router, prefix="", tags=["Search"])
api.include_router(transform.router, prefix="", tags=["Transform"])

app.include_router(api)

if __name__ == '__main__':
    uvicorn.run("efi_api.main:app", host='0.0.0.0', port=8000)
