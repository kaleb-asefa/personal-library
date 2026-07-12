from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..security import hash_password, verify_password

router = APIRouter(prefix="/auth")


def _redirect_with_error(path: str, code: str) -> RedirectResponse:
    return RedirectResponse(url=f"{path}?error={code}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/signup", include_in_schema=False)
async def signup(
    request: Request,
    username: Annotated[str, Form(...)],
    email: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    username = username.strip()
    email = email.strip().lower()

    if len(password) < 8:
        return _redirect_with_error("/signup", "short_password")

    if await db.scalar(select(User).where(func.lower(User.username) == username.lower())):
        return _redirect_with_error("/signup", "username_taken")

    if await db.scalar(select(User).where(func.lower(User.email) == email.lower())):
        return _redirect_with_error("/signup", "email_taken")

    user = User(username=username, email=email, password_hash=hash_password(password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    request.session["user_id"] = user.user_id
    request.session["username"] = user.username
    request.session["email"] = user.email
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/login", include_in_schema=False)
async def login(
    request: Request,
    email: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if not user or not verify_password(password, user.password_hash):
        return _redirect_with_error("/login", "invalid")

    request.session["user_id"] = user.user_id
    request.session["username"] = user.username
    request.session["email"] = user.email
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout", include_in_schema=False)
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
