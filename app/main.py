from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from ..orm import Book, Author, Genre, get_session
from ..queries import get_all_books, mark_book_as_read, get_books_by_genre, get_books_by_author, top_rated_books

from pathlib import Path

BASE_DIR = Path(__file__).parent  # goes up from app/ to project root

print(f"BASE_DIR: {BASE_DIR}")  # Debugging line to check the base directory

app = FastAPI()


templates = Jinja2Templates(directory=BASE_DIR / 'templates')




@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {'books': get_all_books()})