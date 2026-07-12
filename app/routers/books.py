from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from ..db import get_db
from ..deps import get_current_user
from ..models import Author, Book, Genre, User
from ..templating import templates

router = APIRouter()


def _bad_request(path: str, code: str) -> RedirectResponse:
    return RedirectResponse(url=f"{path}?error={code}", status_code=status.HTTP_303_SEE_OTHER)


async def resolve_author(db: AsyncSession, name: str) -> Author:
    """Find an author by name (case-insensitive) or create a new one."""
    cleaned = name.strip()
    existing = await db.scalar(select(Author).where(func.lower(Author.name) == cleaned.lower()))
    if existing:
        return existing
    author = Author(name=cleaned, country="")
    db.add(author)
    await db.flush()
    return author


async def load_genres(db: AsyncSession) -> list[Genre]:
    result = await db.execute(select(Genre).order_by(Genre.name))
    return list(result.scalars().all())


@router.get("/books/new", response_class=HTMLResponse, include_in_schema=False)
async def add_book_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    genres = await load_genres(db)
    return templates.TemplateResponse(
        request,
        "book_form.html",
        {"user": user, "genres": genres, "mode": "add", "selected_genre_ids": set()},
    )


@router.post("/books/new", include_in_schema=False)
async def create_book(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    title: Annotated[str, Form(...)],
    author_name: Annotated[str, Form(...)],
    published_year: Annotated[int, Form(...)],
    genre_ids: Annotated[list[int], Form()] = [],  # noqa: B006 - FastAPI requires mutable default
    status_value: Annotated[str, Form(alias="status")] = "unread",
):
    # get_current_user raised 401 if the visitor isn't logged in.
    title = title.strip()
    author_name = author_name.strip()
    if not title or not author_name:
        return _bad_request("/books/new", "required")

    if status_value not in ("unread", "reading", "read"):
        status_value = "unread"

    author = await resolve_author(db, author_name)
    genres = (
        list((await db.execute(select(Genre).where(Genre.genre_id.in_(genre_ids)))).scalars().all())
        if genre_ids
        else []
    )

    book = Book(
        title=title,
        author=author,
        published_year=published_year,
        status=status_value,
        rating=0,
        user=user,
        genres=genres,
    )
    db.add(book)
    await db.commit()
    return RedirectResponse(url=f"/books/{book.book_id}", status_code=status.HTTP_303_SEE_OTHER)


async def _load_book(db: AsyncSession, book_id: int) -> Book:
    result = await db.execute(
        select(Book)
        .where(Book.book_id == book_id)
        .options(joinedload(Book.author), selectinload(Book.genres), joinedload(Book.user))
    )
    book = result.unique().scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return book


@router.get("/books/{book_id}", response_class=HTMLResponse, include_in_schema=False)
async def book_detail_page(
    book_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    book = await _load_book(db, book_id)
    user_id = request.session.get("user_id")
    return templates.TemplateResponse(
        request,
        "book_detail.html",
        {"book": book, "owner_id": user_id, "is_owner": user_id == book.user_id},
    )


@router.get("/books/{book_id}/edit", response_class=HTMLResponse, include_in_schema=False)
async def edit_book_page(
    book_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    book = await _load_book(db, book_id)
    if book.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your book")
    genres = await load_genres(db)
    return templates.TemplateResponse(
        request,
        "book_form.html",
        {
            "user": user,
            "book": book,
            "genres": genres,
            "mode": "edit",
            "selected_genre_ids": {g.genre_id for g in book.genres},
        },
    )


@router.post("/books/{book_id}/edit", include_in_schema=False)
async def update_book(
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    title: Annotated[str, Form(...)],
    author_name: Annotated[str, Form(...)],
    published_year: Annotated[int, Form(...)],
    status_value: Annotated[str, Form(alias="status")] = "unread",
    rating: Annotated[int, Form(...)] = 0,
    genre_ids: Annotated[list[int], Form()] = [],  # noqa: B006
):
    book = await _load_book(db, book_id)
    if book.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your book")

    title = title.strip()
    author_name = author_name.strip()
    if not title or not author_name:
        return _bad_request(f"/books/{book_id}/edit", "required")

    if status_value not in ("unread", "reading", "read"):
        status_value = "unread"
    rating = max(0, min(5, int(rating)))

    book.title = title
    book.author = await resolve_author(db, author_name)
    book.published_year = published_year
    book.status = status_value
    book.rating = rating

    if genre_ids:
        result = await db.execute(select(Genre).where(Genre.genre_id.in_(genre_ids)))
        book.genres = list(result.scalars().all())
    else:
        book.genres = []

    await db.commit()
    return RedirectResponse(url=f"/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/books/{book_id}/delete", include_in_schema=False)
async def delete_book(
    book_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    book = await _load_book(db, book_id)
    if book.user_id != user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your book")
    await db.delete(book)
    await db.commit()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
