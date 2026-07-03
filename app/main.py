from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from typing import Annotated

from sqlalchemy import select
from sqlalchemy.orm import joinedload, Session
from ..orm import Book, Author, Genre, get_db, User
from ..queries import get_all_books, mark_book_as_read, get_books_by_genre, get_books_by_author, top_rated_books

from .schema import UserCreate, UserResponse, booksResponse

from pathlib import Path

BASE_DIR = Path(__file__).parent  # goes up from app/ to project root

app = FastAPI()


templates = Jinja2Templates(directory=BASE_DIR / 'templates')




@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    books = db.execute(select(Book).options(joinedload(Book.author), joinedload(Book.genres))).scalars().unique().all()
    return templates.TemplateResponse(request, "index.html", {'books': books})


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

@app.get('/api/books', response_model=list[booksResponse])
def api_books(db : Annotated[Session, Depends(get_db)]):
    return get_all_books(db)

@app.get('/api/books/{book_id}', response_model=booksResponse)
def api_book_detail(book_id: int, db: Session = Depends(get_db)):
    book = db.execute(select(Book).where(
        Book.book_id == book_id).options(
            joinedload(Book.author), 
            joinedload(Book.genres))).unique().scalar_one_or_none()
    if book:
        return book
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    
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
