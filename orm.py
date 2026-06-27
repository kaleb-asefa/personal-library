from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

engine = create_engine('sqlite:///library.db')

Base = declarative_base()

class Book(Base):
    __tablename__ = 'books'
    book_id = Column(Integer, primary_key=True)
    title = Column(String)
    author_id = Column(Integer, ForeignKey('authors.author_id'))
    published_year = Column(Integer)
    status = Column(String)
    genre_id = Column(Integer, ForeignKey('genres.genre_id'))
    rating = Column(Integer)

    author = relationship("Author", back_populates="books")
    genres = relationship("Genre", back_populates="books")

class Author(Base):
    __tablename__ = 'authors'
    author_id = Column(Integer, primary_key=True)
    name = Column(String)
    country = Column(String)

    books = relationship("Book", back_populates="author")

class Genre(Base):
    __tablename__ = 'genres'
    genre_id = Column(Integer, primary_key=True)
    name = Column(String)

    books = relationship("Book", back_populates="genres")

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

session.commit()