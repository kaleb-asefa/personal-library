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
from .models import Book, Genre, User
from .routers import auth, books, users
from .templating import templates

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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from .db import AsyncSessionLocal

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

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(users.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Shelf home. Logged-out visitors land on the login page."""
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    user = await db.scalar(select(User).where(User.user_id == user_id))
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    books_result = await db.execute(
        select(Book)
        .where(Book.user_id == user_id)
        .options(selectinload(Book.author), selectinload(Book.genres))
        .order_by(Book.created_at.desc())
    )
    all_books = list(books_result.scalars().unique().all())

    reading = [b for b in all_books if b.status == "reading"]
    up_next = [b for b in all_books if b.status == "unread"]
    finished = [b for b in all_books if b.status == "read"]

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "user": user,
            "reading": reading,
            "up_next": up_next,
            "finished": finished,
            "total_books": len(all_books),
            "read_count": len(finished),
        },
    )


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@app.get("/signup", response_class=HTMLResponse, include_in_schema=False)
async def signup_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "signup.html", {})
