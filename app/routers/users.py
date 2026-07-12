from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..models import Book, User
from ..security import hash_password, verify_password
from ..templating import templates

router = APIRouter()


def _redirect_with_error(path: str, code: str) -> RedirectResponse:
    return RedirectResponse(url=f"{path}?error={code}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/users/me/edit", response_class=HTMLResponse, include_in_schema=False)
async def edit_profile_page(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    return templates.TemplateResponse(request, "profile_edit.html", {"user": user})


@router.post("/users/me/edit", include_in_schema=False)
async def update_profile(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    username: Annotated[str, Form(...)],
    email: Annotated[str, Form(...)],
    current_password: Annotated[str | None, Form()] = None,
    new_password: Annotated[str | None, Form()] = None,
):
    username = username.strip()
    email = email.strip().lower()

    # Username / email uniqueness (excluding the current user).
    if username.lower() != user.username.lower():
        if await db.scalar(
            select(User).where(func.lower(User.username) == username.lower(), User.user_id != user.user_id)
        ):
            return _redirect_with_error("/users/me/edit", "username_taken")

    if email.lower() != user.email.lower():
        if await db.scalar(
            select(User).where(func.lower(User.email) == email.lower(), User.user_id != user.user_id)
        ):
            return _redirect_with_error("/users/me/edit", "email_taken")

    # Changing the password requires confirming the current one.
    if new_password:
        if len(new_password) < 8:
            return _redirect_with_error("/users/me/edit", "short_password")
        if not current_password or not verify_password(current_password, user.password_hash):
            return _redirect_with_error("/users/me/edit", "wrong_password")
        user.password_hash = hash_password(new_password)

    user.username = username
    user.email = email
    await db.commit()
    await db.refresh(user)

    request.session["username"] = user.username
    request.session["email"] = user.email
    return RedirectResponse(url="/users/me", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/users/me", response_class=HTMLResponse, include_in_schema=False)
async def profile_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # Fresh book counts for the profile stats.
    books = await db.scalars(select(Book).where(Book.user_id == user.user_id))
    books = list(books.all())
    read_count = sum(1 for b in books if b.status == "read")
    reading_count = sum(1 for b in books if b.status == "reading")
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "user": user,
            "total_books": len(books),
            "read_count": read_count,
            "reading_count": reading_count,
        },
    )


@router.post("/users/me/delete", include_in_schema=False)
async def delete_account(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await db.delete(user)
    await db.commit()
    request.session.clear()
    return RedirectResponse(url="/signup", status_code=status.HTTP_303_SEE_OTHER)
