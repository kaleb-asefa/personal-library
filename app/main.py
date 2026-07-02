from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from sqlalchemy import select
from sqlalchemy.orm import joinedload, Session
from ..orm import Book, Author, Genre, get_db
from ..queries import get_all_books, mark_book_as_read, get_books_by_genre, get_books_by_author, top_rated_books

from .schema import UserCreate, UserResponse, booksResponse

from pathlib import Path

BASE_DIR = Path(__file__).parent  # goes up from app/ to project root

print(f"BASE_DIR: {BASE_DIR}")  # Debugging line to check the base directory

app = FastAPI()


templates = Jinja2Templates(directory=BASE_DIR / 'templates')




@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    books = db.execute(select(Book).options(joinedload(Book.author), joinedload(Book.genres))).scalars().unique().all()
    return templates.TemplateResponse(request, "index.html", {'books': books})

@app.get('/api/books', response_model=list[booksResponse])
def api_books():
    return get_all_books()

@app.get('/api/books/{book_id}', response_model=booksResponse)
def api_book_detail(book_id: int):
    with get_db() as session:
        book = session.execute(select(Book).where(
            Book.book_id == book_id).options(
                joinedload(Book.author), 
                joinedload(Book.genres))).unique().scalar_one_or_none()
        if book:
            return book
        raise HTTPException(status_code=404, detail="Book not found")
    
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
