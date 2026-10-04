from fastapi import FastAPI, Request, HTTPException, status, Depends, Query, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

from typing import Annotated

from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import CurrentUser, require_owner, hash_password, verify_password
from .deps import get_current_user

from pathlib import Path
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import Base, engine, get_db
from .models import Author, Book, Genre, User
from .routers import auth, books, user
from .templating import templates
from .db import AsyncSessionLocal

BASE_DIR = Path(__file__).resolve().parent

# Reference genres seeded on first run so the add-book picker is useful.
SEED_GENRES = [
    "Science Fiction",
    "Fantasy",
    "Literary Fiction",
    "Mystery",
    "Thriller",
    "Historical Fiction",
    "Horror",
    "Romance",
    "Biography",
    "Nonfiction",
    "Poetry",
    "Young Adult",
]


async def seed_genres(db: AsyncSession) -> None:
    existing = {g.name for g in (await db.execute(select(Genre))).scalars().all()}
    missing = [Genre(name=name) for name in SEED_GENRES if name not in existing]
    if missing:
        db.add_all(missing)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):

    async with AsyncSessionLocal() as session:
        await seed_genres(session)
    yield
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key.get_secret_value(),
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/media", StaticFiles(directory=BASE_DIR / "media"), name="media")

app.include_router(auth.router)
app.include_router(books.router, prefix="/api/books")
app.include_router(user.api_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse(url=f"/users/{user_id}/books", status_code=303)
    return templates.TemplateResponse(request, "index.html", {})

@app.get("/users", response_class=HTMLResponse, include_in_schema=False)
async def users_page(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request, "users.html", {"users": [current_user]})

@app.get("/users/new", response_class=HTMLResponse, include_in_schema=False)
def create_user_page(request: Request):
    return templates.TemplateResponse(request, "create_user.html")

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@app.get("/forgot-password", response_class=HTMLResponse, include_in_schema=False)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html")


@app.get("/reset-password", response_class=HTMLResponse, include_in_schema=False)
def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse(request, "reset_password.html", {"token": token})

@app.get("/logout", response_class=HTMLResponse, include_in_schema=False)
def logout_page(request: Request, current_user: CurrentUser):
    return templates.TemplateResponse(request, "logout.html")


def _redirect_with_error(path: str, code: str) -> RedirectResponse:
    return RedirectResponse(url=f"{path}?error={code}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/users/me/edit", response_class=HTMLResponse, include_in_schema=False)
async def edit_profile_page(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
):
    return templates.TemplateResponse(request, "profile_edit.html", {"user": user})


@app.post("/users/me/edit", include_in_schema=False)
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


@app.get("/users/me", response_class=HTMLResponse, include_in_schema=False)
async def profile_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    books = await db.scalars(select(Book).where(Book.user_id == user.user_id))
    books = list(books.all())
    read_count = sum(1 for book in books if book.status == "read")
    reading_count = sum(1 for book in books if book.status == "reading")
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


@app.post("/users/me/delete", include_in_schema=False)
async def delete_account(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    await db.delete(user)
    await db.commit()
    request.session.clear()
    return RedirectResponse(url="/signup", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/users/{user_id}/edit", response_class=HTMLResponse, include_in_schema=False)
async def edit_user_page(user_id: int, request: Request, current_user: CurrentUser):
    require_owner(user_id, current_user)
    return templates.TemplateResponse(request, "edit_user.html", {"user": current_user})


@app.get("/users/{user_id}/delete", response_class=HTMLResponse, include_in_schema=False)
async def delete_user_page(user_id: int, request: Request, current_user: CurrentUser):
    require_owner(user_id, current_user)
    return templates.TemplateResponse(request, "delete_user.html", {"user": current_user})

@app.get("/users/{user_id}", response_class=HTMLResponse, include_in_schema=False)
async def user_detail_page(
    user_id: int,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_owner(user_id, current_user)
    user = await db.execute(
        select(User)
        .where(User.user_id == user_id)
        .options(
            joinedload(User.books).joinedload(Book.author),
            joinedload(User.books).selectinload(Book.genres),
            joinedload(User.books).joinedload(Book.user)
        )
    )
    user = user.unique().scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return templates.TemplateResponse(request, "user_detail.html", {"user": user, "books": user.books})

@app.get("/users/{user_id}/books", response_class=HTMLResponse, include_in_schema=False)
async def user_books_page(
    user_id: int,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    require_owner(user_id, current_user)

    total = await db.execute(
        select(func.count(Book.book_id))
        .where(Book.user_id == current_user.user_id)
    )
    total = total.scalar_one() or 0
    
    books = await db.execute(
        select(Book)
        .where(Book.user_id == current_user.user_id)
        .order_by(Book.published_year.desc())
        .offset(skip)
        .limit(limit)
        .options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))
    )
    books = books.scalars().unique().all()
    return templates.TemplateResponse(
        request,
        "user_books.html",
        {
            "user": current_user,
            "books": books,
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": skip + len(books) < total,
        },
    )

@app.get("/books/new", response_class=HTMLResponse, include_in_schema=False)
async def add_book_page(
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    authors = await db.execute(select(Author).order_by(Author.name))
    authors = authors.scalars().all()
    genres = await db.execute(select(Genre).order_by(Genre.name))
    genres = genres.scalars().all()
    return templates.TemplateResponse(
        request,
        "add_book.html",
        {"authors": authors, "genres": genres},
    )

@app.get("/books/{book_id}", response_class=HTMLResponse, include_in_schema=False)
async def book_detail_page(
    book_id: int,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    book = await db.execute(
        select(Book)
        .where(Book.book_id == book_id)
        .options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))
    )
    book = book.unique().scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    require_owner(book.user_id, current_user)
    return templates.TemplateResponse(request, "book_detail.html", {"book": book})

@app.get("/books/{book_id}/edit", response_class=HTMLResponse, include_in_schema=False)
async def edit_book_page(
    book_id: int,
    request: Request,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    book = await db.execute(
        select(Book)
        .where(Book.book_id == book_id)
        .options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))
    )
    book = book.unique().scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    require_owner(book.user_id, current_user)
    
    authors = await db.execute(select(Author).order_by(Author.name))
    authors = authors.scalars().all()
    genres = await db.execute(select(Genre).order_by(Genre.name))
    genres = genres.scalars().all()
    selected_genre_ids = {genre.genre_id for genre in book.genres}
    return templates.TemplateResponse(
        request,
        "edit_book.html",
        {
            "book": book,
            "authors": authors,
            "genres": genres,
            "selected_genre_ids": selected_genre_ids,
        },
    )


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


    
@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if (
        exc.status_code == status.HTTP_401_UNAUTHORIZED
        and request.method == "GET"
        and not request.url.path.startswith("/api/")
    ):
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=status.HTTP_303_SEE_OTHER)
    if (
        exc.status_code == status.HTTP_403_FORBIDDEN
        and request.method == "GET"
        and not request.url.path.startswith("/api/")
    ):
        return templates.TemplateResponse(
            request,
            "forbidden.html",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return await http_exception_handler(request, exc)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return await request_validation_exception_handler(request, exc)
