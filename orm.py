from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, Enum, CheckConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from contextlib import contextmanager

engine = create_engine('sqlite:///library.db', echo=True)

Base = declarative_base()

books_genres = Table('books_genres', Base.metadata,
    Column('book_id', Integer, ForeignKey('books.book_id')),
    Column('genre_id', Integer, ForeignKey('genres.genre_id')))

class Book(Base):
    __tablename__ = 'books'
    book_id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    author_id = Column(Integer, ForeignKey('authors.author_id'), nullable=False)
    published_year = Column(Integer)
    status = Column(Enum('read', 'unread', name='status_enum'), nullable=False)
    rating = Column(Integer, CheckConstraint('rating >= 1 AND rating <= 5'), nullable=True)

    author = relationship("Author", back_populates="books")
    genres = relationship("Genre", secondary='books_genres', back_populates="books")

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



Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine, expire_on_commit=False)

@contextmanager
def get_session():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
