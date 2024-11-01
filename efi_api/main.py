from pathlib import Path

import uvicorn
from fastapi import FastAPI

from .routers import hello,efi,health,search

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
    openapi_tags=tags_metadata,
)

app.include_router(hello.router, prefix='/hello', tags=['hello'])
app.include_router(efi.router, prefix="/efi/v1", tags=["EFI"])
app.include_router(health.router, tags=["Health"])
app.include_router(search.router, prefix="", tags=["Search"])

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
