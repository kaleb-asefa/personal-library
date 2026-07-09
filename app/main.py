from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler

from typing import Annotated

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload, Session
from sqlalchemy.ext.asyncio import AsyncSession

from ..orm import Book, Author, Genre, get_db, User, Base, engine, AsyncSessionLocal

from .schema import UserCreate, UserResponse, booksResponse, booksCreate, booksUpdate, UserUpdate

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

templates = Jinja2Templates(directory=BASE_DIR / 'templates')
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")




@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    books = await db.execute(select(Book).options(selectinload(Book.author), selectinload(Book.genres), selectinload(Book.user)))
    books = books.scalars().unique().all()
    return templates.TemplateResponse(request, "index.html", {'books': books})

@app.get("/users", response_class=HTMLResponse, include_in_schema=False)
async def users_page(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    users = await db.execute(select(User).options(selectinload(User.books)))
    users = users.scalars().unique().all()
    return templates.TemplateResponse(request, "users.html", {"users": users})

@app.get("/users/new", response_class=HTMLResponse, include_in_schema=False)
def create_user_page(request: Request):
    return templates.TemplateResponse(request, "create_user.html")

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
    user = user.scalar_one_or_none()
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
    authors = db.execute(select(Author).order_by(Author.name)).scalars().all()
    genres = db.execute(select(Genre).order_by(Genre.name)).scalars().all()
    users = db.execute(select(User).order_by(User.username)).scalars().all()
    return templates.TemplateResponse(
        request,
        "add_book.html",
        {"authors": authors, "genres": genres, "users": users},
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
    book = await db.execute(
        select(Book)
        .where(Book.book_id == book_id)
        .options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))
    )
    book = book.unique().scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    
    authors = await db.execute(select(Author).order_by(Author.name))
    authors = authors.scalars().all()
    genres = await db.execute(select(Genre).order_by(Genre.name))
    genres = genres.scalars().all()
    users = await db.execute(select(User).order_by(User.username))
    users = users.scalars().all()
    selected_genre_ids = {genre.genre_id for genre in book.genres}
    return templates.TemplateResponse(
        request,
        "edit_book.html",
        {
            "book": book,
            "authors": authors,
            "genres": genres,
            "users": users,
            "selected_genre_ids": selected_genre_ids,
        },
    )



@app.post("/api/users", response_model=UserResponse)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(User).where(User.username == user.username))
    result = result.first()
    if result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    
    result = await db.execute(select(User).where(User.email == user.email))
    result = result.first()
    if result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
    
    new_user = User(username=user.username, email=user.email, password=user.password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user, attribute_names=['username', 'email', 'password'])
    return new_user

@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@app.get("/api/users/{user_id}/books", response_model=list[booksResponse])
async def get_user_books(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    books = db.execute(select(Book).where(Book.user_id == user_id).options(joinedload(Book.author), joinedload(Book.genres))).scalars().unique().all()
    return books

@app.patch("/api/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_update: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updated_data = user_update.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user, attribute_names=['username', 'email', 'password'])
    return user

@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)
    await db.commit()

@app.get('/api/books', response_model=list[booksResponse])
async def api_books(db : Annotated[AsyncSession, Depends(get_db)]):
    books = await db.execute(select(Book).options(joinedload(Book.author), selectinload(Book.genres), joinedload(Book.user)))
    books = books.scalars().unique().all()
    return books

@app.post('/api/books', response_model=booksResponse)
async def api_create_book(book: booksCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    author = await db.execute(select(Author).where(Author.author_id == book.author_id))
    author = author.scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    
    user = await db.execute(select(User).where(User.user_id == book.user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    genres = db.execute(select(Genre).where(Genre.genre_id.in_(book.genre_ids)))
    genres = genres.scalars().all()
    if len(genres) != len(book.genre_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
    
    new_book = Book(
        title=book.title,
        author=author,
        published_year=book.published_year,
        status='unread',
        rating=0,
        user=user,
        genres=genres
    )
    
    db.add(new_book)
    await db.commit()
    await db.refresh(new_book, attribute_names=['author', 'user', 'genres'])
    
    return new_book

@app.get('/api/books/{book_id}', response_model=booksResponse)
async def api_book_detail(book_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(
        Book.book_id == book_id).options(
            joinedload(Book.author), 
            selectinload(Book.genres),
            joinedload(Book.user)))
    book = book.scalar_one_or_none()
    if book:
        return book
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

@app.put('/api/books/{book_id}', response_model=booksResponse)
async def update_book_full(book_id: int, book_update: booksCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(Book.book_id == book_id))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    
    author = await db.execute(select(Author).where(Author.author_id == book_update.author_id))
    author = author.scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    
    user = await db.execute(select(User).where(User.user_id == book_update.user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    genres = await db.execute(select(Genre).where(Genre.genre_id.in_(book_update.genre_ids)))
    genres = genres.scalars().all()
    if len(genres) != len(book_update.genre_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
    
    book.title = book_update.title
    book.author = author
    book.published_year = book_update.published_year
    book.user = user
    book.genres = genres
    
    await db.commit()
    await db.refresh(book, attribute_names=['author', 'user', 'genres'])
    
    return book

@app.patch('/api/books/{book_id}', response_model=booksResponse)
async def update_book_partial(book_id: int, book_update: booksUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(Book.book_id == book_id).options(joinedload(Book.author), selectinload(Book.genres), joinedload(Book.user)))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    updated_data = book_update.model_dump(exclude_unset=True)

    if 'author_id' in updated_data:
        author = await db.execute(select(Author).where(Author.author_id == updated_data['author_id']))
        author = author.scalar_one_or_none()
        if not author:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
        book.author = author

    if 'user_id' in updated_data:
        user = await db.execute(select(User).where(User.user_id == updated_data['user_id']))
        user = user.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        book.user = user

    if 'genre_ids' in updated_data:
        genres = await db.execute(select(Genre).where(Genre.genre_id.in_(updated_data['genre_ids'])))
        genres = genres.scalars().all()
        if len(genres) != len(updated_data['genre_ids']):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
        book.genres = genres
    for key, value in updated_data.items():
        if key not in ['author_id', 'user_id', 'genre_ids']:
            setattr(book, key, value)
    await db.commit()
    await db.refresh(book, attribute_names=['author', 'user', 'genres'])
    return book

@app.delete('/api/books/{book_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(Book.book_id == book_id))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    db.delete(book)
    db.commit()

    
@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exc: StarletteHTTPException):
    return await http_exception_handler(request, exc)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return await request_validation_exception_handler(request, exc)
