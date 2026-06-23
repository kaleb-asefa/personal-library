from sqlalchemy import create_engine, Column, Integer, String, Table, MetaData, ForeignKey

engine = create_engine('sqlite:///library.db')

metadata = MetaData()

books = Table('books', metadata,
              Column('book_id', Integer, primary_key=True),
              Column('title', String),
              Column('author_id', Integer, ForeignKey('authors.author_id')),
              Column('published_year', Integer),
              Column('status', String),
              Column('genre_id', Integer, ForeignKey('genres.genre_id')),
              Column('rating', Integer))

authors = Table('authors', metadata,
                Column('author_id', Integer, primary_key=True),
                Column('name', String),
                Column('country', String))

genres = Table('genres', metadata,
               Column('genre_id', Integer, primary_key=True),
               Column('name', String))