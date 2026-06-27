from orm import Base, Book, Author, Genre, get_session

def get_all_books():
    with get_session() as session:
        return session.query(Book).all()
    
def mark_book_as_read(name):
    with get_session() as session:
        book = session.query(Book).filter_by(title=name).first()
        if book:
            book.status = 'read'
            session.commit()
            return True
        return False  
    
def get_books_by_genre(genre_name):
    with get_session() as session:
        genre = session.query(Genre).filter_by(name=genre_name).first()
        if genre:
            return genre.books
        return []
    
def get_books_by_author(author_name):
    with get_session() as session:
        author = session.query(Author).filter_by(name=author_name).first()
        if author:
            return author.books
        return []
    
def top_rated_books(min_rating=4):
    with get_session() as session:
        return session.query(Book).filter(Book.rating >= min_rating).all()
    
get_all_books()