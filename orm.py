from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, Enum, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, Mapped, mapped_column
from contextlib import contextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

engine = create_async_engine('sqlite+aiosqlite:///library.db', echo=True, future=True)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    user_id : Mapped[int] = mapped_column(Integer, primary_key=True)
    username : Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email : Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash : Mapped[str] = mapped_column(String(200), nullable=False)

    books : Mapped[list['Book']] = relationship("Book", back_populates="user", cascade="all, delete-orphan")
    image_file : Mapped[str | None] = mapped_column(String, nullable=True)

    @property
    def image_path(self):
        if self.image_file:
            return f"/media/profile/{self.image_file}"
        return f"/static/profile/default.jpg"

    def __repr__(self):
        return self.username

books_genres = Table('books_genres', Base.metadata,
    Column('book_id', Integer, ForeignKey('books.book_id'), primary_key=True),
    Column('genre_id', Integer, ForeignKey('genres.genre_id'), primary_key=True))

class Book(Base):
    __tablename__ = 'books'
    book_id : Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title : Mapped[str] = mapped_column(String)
    author_id : Mapped[int] = mapped_column(Integer, ForeignKey('authors.author_id'), index=True)
    published_year : Mapped[int] = mapped_column(Integer)
    status : Mapped[str] = mapped_column(Enum('read', 'unread', name='status_enum'), default='unread')
    rating : Mapped[int] = mapped_column(Integer, CheckConstraint('rating >= 0 AND rating <= 5'), default=0)
    user_id : Mapped[int] = mapped_column(Integer, ForeignKey('users.user_id'), index=True)

    author = relationship("Author", back_populates="books")
    genres = relationship("Genre", secondary='books_genres', back_populates="books")
    user = relationship("User", back_populates="books")

    def __repr__(self):
        return self.title

class Author(Base):
    __tablename__ = 'authors'
    author_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    country = Column(String)

    books = relationship("Book", back_populates="author")

    def __repr__(self):
        return self.name

class Genre(Base):
    __tablename__ = 'genres'
    genre_id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    books = relationship("Book", secondary='books_genres', back_populates="genres")

    def __repr__(self):
        return self.name





AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

 
@contextmanager   
def get_db_session():
    db = AsyncSessionLocal()
    try:
        yield db
        db.commit()
    finally:
        db.close()