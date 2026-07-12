# The Stacks

A personal reading log — add books to your shelf, move them from *up next* to *currently reading* to *finished*, and rate them when you're done.

Built with **FastAPI**, **async SQLAlchemy** (aiosqlite), and server-rendered Jinja2 templates.

## Run it

```bash
uv run uvicorn app.main:app --reload
```

Then open <http://localhost:8000>.

On first run the app creates `library.db` at the project root and seeds a list of reference genres so the add-book picker is ready to use.

## What it does

- **Sign up / log in** — session-based auth, one account per shelf.
- **Add a book** — title, author (typed, not picked), year, status, genres. Authors are matched or created automatically.
- **Track status** — *Up next* → *Currently reading* → *Finished*.
- **Rate** finished books from 0–5 stars.
- **Profile** — edit username / email / password; delete account (cascades to its books).

## Notes

- All book forms post plain HTML and redirect — no client-side framework required.
- The only JavaScript is a delete-confirmation prompt; everything else works without it.

## Project layout

```
app/
  main.py        FastAPI app, lifespan (creates tables, seeds genres), page routes
  db.py          async engine, Base, get_db
  models.py      User, Author, Genre, Book, books_genres
  security.py    password hashing
  deps.py        get_current_user dependency
  templating.py  Jinja2 templates
  routers/       auth, books, users
  templates/     base, index (shelf), login, signup, book_detail, book_form, profile, profile_edit
  static/        css/style.css, js/app.js
```
