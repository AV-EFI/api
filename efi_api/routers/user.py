from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse

from ..schemas.auth import Token
from ..helpers.auth import valid_access_token
from .auth import login


router = APIRouter()


@router.get('/session', response_model=Token)
async def session(request: Request) -> Any:
    try:
        return valid_access_token(request)
    except HTTPException:
        return RedirectResponse(url=request.url_for('login'))


@router.get('/logout')
async def logout(request: Request):
    request.session.pop('token', None)
    return RedirectResponse(url='/')
