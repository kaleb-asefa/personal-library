from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

from typing import Annotated

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..orm import Book, Genre, get_db, User, Base, engine
from .config import settings

from .routers import user, books

from pathlib import Path
from contextlib import asynccontextmanager

BASE_DIR = Path(__file__).parent  # goes up from app/ to project root

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown code
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key.get_secret_value(), same_site="lax")

templates = Jinja2Templates(directory=BASE_DIR / 'templates')

app.include_router(user.router, prefix="/api/users", tags=["users"])
app.include_router(books.router, prefix="/api/books", tags=["books"])

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")




@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    user_id = request.session.get("user_id")

    if not user_id:
        return templates.TemplateResponse(request, "login.html", {"show_home_link": False})

    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        request.session.clear()
        return templates.TemplateResponse(request, "login.html", {"show_home_link": False})

    books = await db.execute(
        select(Book)
        .where(Book.user_id == user_id)
        .options(selectinload(Book.author), selectinload(Book.genres), selectinload(Book.user))
    )
    books = books.scalars().unique().all()
    read_count = sum(1 for book in books if book.status == "read")
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "books": books,
            "current_user": user,
            "current_user_id": user.user_id,
            "read_count": read_count,
        },
    )

@app.get("/users", response_class=HTMLResponse, include_in_schema=False)
async def users_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    user_id = request.session.get("user_id")
    if not user_id:
        return templates.TemplateResponse(request, "login.html", {"show_home_link": False})

    user = await db.execute(select(User).where(User.user_id == user_id).options(selectinload(User.books)))
    user = user.unique().scalar_one_or_none()
    if not user:
        request.session.clear()
        return templates.TemplateResponse(request, "login.html", {"show_home_link": False})

    return templates.TemplateResponse(request, "users.html", {"users": [user], "current_user": user, "current_user_id": user.user_id})

@app.get("/users/new", response_class=HTMLResponse, include_in_schema=False)
def create_user_page(request: Request):
    return templates.TemplateResponse(request, "create_user.html")

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/logout", response_class=HTMLResponse, include_in_schema=False)
def logout_page(request: Request):
    return templates.TemplateResponse(request, "logout.html")

@app.get("/users/{user_id}/edit", response_class=HTMLResponse, include_in_schema=False)
async def edit_user_page(user_id: int, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return templates.TemplateResponse(request, "edit_user.html", {"user": user})

@app.get("/users/{user_id}", response_class=HTMLResponse, include_in_schema=False)
async def user_detail_page(user_id: int, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
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
async def user_books_page(user_id: int, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    books = await db.execute(
        select(Book)
        .where(Book.user_id == user_id)
        .options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))
    )
    books = books.scalars().unique().all()
    return templates.TemplateResponse(request, "user_books.html", {"user": user, "books": books})

@app.get("/books/new", response_class=HTMLResponse, include_in_schema=False)
async def add_book_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    user_id = request.session.get("user_id")
    if not user_id:
        return templates.TemplateResponse(request, "login.html", {"show_home_link": False})

    genres = await db.execute(select(Genre).order_by(Genre.name))
    genres = genres.scalars().all()
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    return templates.TemplateResponse(
        request,
        "add_book.html",
        {"genres": genres, "current_user": user, "current_user_id": user.user_id},
    )

@app.get("/books/{book_id}", response_class=HTMLResponse, include_in_schema=False)
async def book_detail_page(book_id: int, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(
        select(Book)
        .where(Book.book_id == book_id)
        .options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))
    )
    book = book.unique().scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return templates.TemplateResponse(request, "book_detail.html", {"book": book})

@app.get("/books/{book_id}/edit", response_class=HTMLResponse, include_in_schema=False)
async def edit_book_page(book_id: int, request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    user_id = request.session.get("user_id")
    if not user_id:
        return templates.TemplateResponse(request, "login.html", {"show_home_link": False})

    book = await db.execute(
        select(Book)
        .where(Book.book_id == book_id)
        .options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))
    )
    book = book.unique().scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    
    genres = await db.execute(select(Genre).order_by(Genre.name))
    genres = genres.scalars().all()
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    selected_genre_ids = {genre.genre_id for genre in book.genres}
    return templates.TemplateResponse(
        request,
        "edit_book.html",
        {
            "book": book,
            "genres": genres,
            "current_user": user,
            "current_user_id": user.user_id,
            "selected_genre_ids": selected_genre_ids,
        },
    )




    
@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return await http_exception_handler(request, exc)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return await request_validation_exception_handler(request, exc)
