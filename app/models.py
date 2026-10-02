from sqlalchemy import (
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Status values a book can hold.
STATUS_VALUES = ("unread", "reading", "read")

# Many-to-many association between books and genres.
books_genres = Table(
    "books_genres",
    Base.metadata,
    Column("book_id", Integer, ForeignKey("books.book_id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.genre_id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    image_file: Mapped[str | None] = mapped_column(String, nullable=True)

    books: Mapped[list["Book"]] = relationship(
        "Book", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def image_path(self) -> str:
        if self.image_file:
            return f"/media/profile/{self.image_file}"
        return "/static/profile/default.png"

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class Author(Base):
    __tablename__ = "authors"

    author_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(255), default="", server_default="")

    books: Mapped[list["Book"]] = relationship("Book", back_populates="author")

    def __repr__(self) -> str:
        return f"<Author {self.name}>"


class Genre(Base):
    __tablename__ = "genres"

    genre_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    books: Mapped[list["Book"]] = relationship(
        "Book", secondary=books_genres, back_populates="genres"
    )

    def __repr__(self) -> str:
        return f"<Genre {self.name}>"


class Book(Base):
    __tablename__ = "books"

    book_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.author_id"), index=True)
    published_year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(*STATUS_VALUES, name="status_enum"),
        nullable=False,
        default="unread",
        server_default="unread",
    )
    rating: Mapped[int] = mapped_column(
        Integer, CheckConstraint("rating >= 0 AND rating <= 5"), nullable=False, default=0
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    author = relationship("Author", back_populates="books")
    genres = relationship("Genre", secondary=books_genres, back_populates="books")
    user = relationship("User", back_populates="books")

    def __repr__(self) -> str:
        return f"<Book {self.title}>"
