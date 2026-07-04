from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from typing import Annotated

from sqlalchemy import select
from sqlalchemy.orm import joinedload, Session
from ..orm import Book, Author, Genre, get_db, User
from ..queries import get_all_books, mark_book_as_read, get_books_by_genre, get_books_by_author, top_rated_books

from .schema import UserCreate, UserResponse, booksResponse, booksCreate, booksUpdate, UserUpdate

from pathlib import Path

BASE_DIR = Path(__file__).parent  # goes up from app/ to project root

app = FastAPI()


templates = Jinja2Templates(directory=BASE_DIR / 'templates')
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")




@app.get("/", include_in_schema=False, response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    books = db.execute(select(Book).options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))).scalars().unique().all()
    return templates.TemplateResponse(request, "index.html", {'books': books})

@app.get("/users", response_class=HTMLResponse, include_in_schema=False)
def users_page(request: Request, db: Session = Depends(get_db)):
    users = db.execute(select(User).options(joinedload(User.books))).scalars().unique().all()
    return templates.TemplateResponse(request, "users.html", {"users": users})

@app.get("/users/new", response_class=HTMLResponse, include_in_schema=False)
def create_user_page(request: Request):
    return templates.TemplateResponse(request, "create_user.html")

@app.get("/users/{user_id}", response_class=HTMLResponse, include_in_schema=False)
def user_detail_page(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.execute(
        select(User)
        .where(User.user_id == user_id)
        .options(
            joinedload(User.books).joinedload(Book.author),
            joinedload(User.books).joinedload(Book.genres),
        )
    ).unique().scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return templates.TemplateResponse(request, "user_detail.html", {"user": user, "books": user.books})

@app.get("/users/{user_id}/books", response_class=HTMLResponse, include_in_schema=False)
def user_books_page(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    books = db.execute(
        select(Book)
        .where(Book.user_id == user_id)
        .options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user))
    ).scalars().unique().all()
    return templates.TemplateResponse(request, "user_books.html", {"user": user, "books": books})

@app.get("/books/new", response_class=HTMLResponse, include_in_schema=False)
def add_book_page(request: Request, db: Session = Depends(get_db)):
    authors = db.execute(select(Author).order_by(Author.name)).scalars().all()
    genres = db.execute(select(Genre).order_by(Genre.name)).scalars().all()
    users = db.execute(select(User).order_by(User.username)).scalars().all()
    return templates.TemplateResponse(
        request,
        "add_book.html",
        {"authors": authors, "genres": genres, "users": users},
    )



@app.post("/api/users", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    result = db.execute(select(User).where(User.username == user.username)).first()
    if result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    
    result = db.execute(select(User).where(User.email == user.email)).first()
    if result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
    
    new_user = User(username=user.username, email=user.email, password=user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/api/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@app.get("/api/users/{user_id}/books", response_model=list[booksResponse])
def get_user_books(user_id: int, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    books = db.execute(select(Book).where(Book.user_id == user_id).options(joinedload(Book.author), joinedload(Book.genres))).scalars().unique().all()
    return books

@app.patch("/api/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updated_data = user_update.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.delete(user)
    db.commit()

@app.get('/api/books', response_model=list[booksResponse])
def api_books(db : Annotated[Session, Depends(get_db)]):
    return get_all_books(db)

@app.post('/api/books', response_model=booksResponse)
def api_create_book(book: booksCreate, db: Session = Depends(get_db)):
    author = db.execute(select(Author).where(Author.author_id == book.author_id)).scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    
    user = db.execute(select(User).where(User.user_id == book.user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    genres = db.execute(select(Genre).where(Genre.genre_id.in_(book.genre_ids))).scalars().all()
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
    db.commit()
    db.refresh(new_book)
    
    return new_book

@app.get('/api/books/{book_id}', response_model=booksResponse)
def api_book_detail(book_id: int, db: Session = Depends(get_db)):
    book = db.execute(select(Book).where(
        Book.book_id == book_id).options(
            joinedload(Book.author), 
            joinedload(Book.genres))).unique().scalar_one_or_none()
    if book:
        return book
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

@app.put('/api/books/{book_id}', response_model=booksResponse)
def update_book_full(book_id: int, book_update: booksCreate, db: Session = Depends(get_db)):
    book = db.execute(select(Book).where(Book.book_id == book_id)).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    
    author = db.execute(select(Author).where(Author.author_id == book_update.author_id)).scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    
    user = db.execute(select(User).where(User.user_id == book_update.user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    genres = db.execute(select(Genre).where(Genre.genre_id.in_(book_update.genre_ids))).scalars().all()
    if len(genres) != len(book_update.genre_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
    
    book.title = book_update.title
    book.author = author
    book.published_year = book_update.published_year
    book.user = user
    book.genres = genres
    
    db.commit()
    db.refresh(book)
    
    return book

@app.patch('/api/books/{book_id}', response_model=booksResponse)
def update_book_partial(book_id: int, book_update: booksUpdate, db: Session = Depends(get_db)):
    book = db.execute(select(Book).where(Book.book_id == book_id)).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    updated_data = book_update.model_dump(exclude_unset=True)

    if 'author_id' in updated_data:
        author = db.execute(select(Author).where(Author.author_id == updated_data['author_id'])).scalar_one_or_none()
        if not author:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
        book.author = author

    if 'genre_ids' in updated_data:
        genres = db.execute(select(Genre).where(Genre.genre_id.in_(updated_data['genre_ids']))).scalars().all()
        if len(genres) != len(updated_data['genre_ids']):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
        book.genres = genres
    for key, value in updated_data.items():
        if key not in ['author_id', 'genre_ids']:
            setattr(book, key, value)
    db.commit()
    db.refresh(book)
    return book

@app.delete('/api/books/{book_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = db.execute(select(Book).where(Book.book_id == book_id)).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    db.delete(book)
    db.commit()

    
@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": "Validation error", "details": exc.errors() }
    )
