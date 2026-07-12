from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Annotated
from ...orm import Book, get_db, Author, Genre, User
from ..schema import booksResponse, booksCreate, booksUpdate
from sqlalchemy.orm import joinedload, selectinload

router = APIRouter()


async def get_current_user_id(request: Request) -> int | None:
    user_id = request.session.get("user_id")
    return int(user_id) if user_id else None


@router.get('', response_model=list[booksResponse])
async def api_books(request: Request, db : Annotated[AsyncSession, Depends(get_db)]):
    user_id = await get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    books = await db.execute(select(Book).where(Book.user_id == user_id).options(joinedload(Book.author), selectinload(Book.genres), joinedload(Book.user)))
    books = books.scalars().unique().all()
    return books

@router.post('', response_model=booksResponse)
async def api_create_book(request: Request, book: booksCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    current_user_id = await get_current_user_id(request)
    if not current_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")

    author = await db.execute(select(Author).where(Author.author_id == book.author_id))
    author = author.scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")

    user = await db.execute(select(User).where(User.user_id == current_user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    genres = await db.execute(select(Genre).where(Genre.genre_id.in_(book.genre_ids)))
    genres = genres.scalars().all()
    if len(genres) != len(book.genre_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
    
    new_book = Book(
        title=book.title,
        author=author,
        published_year=book.published_year,
        status='unread',
        rating=0,
        user=user,
        genres=genres
    )
    
    db.add(new_book)
    await db.commit()
    await db.refresh(new_book, attribute_names=['author', 'user', 'genres'])
    
    return new_book

@router.get('/{book_id}', response_model=booksResponse)
async def api_book_detail(book_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(
        Book.book_id == book_id).options(
            joinedload(Book.author), 
            selectinload(Book.genres),
            joinedload(Book.user)))
    book = book.scalar_one_or_none()
    if book:
        return book
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

@router.put('/{book_id}', response_model=booksResponse)
async def update_book_full(book_id: int, book_update: booksCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(Book.book_id == book_id))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    
    author = await db.execute(select(Author).where(Author.author_id == book_update.author_id))
    author = author.scalar_one_or_none()
    if not author:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
    
    user = await db.execute(select(User).where(User.user_id == book_update.user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    genres = await db.execute(select(Genre).where(Genre.genre_id.in_(book_update.genre_ids)))
    genres = genres.scalars().all()
    if len(genres) != len(book_update.genre_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
    
    book.title = book_update.title
    book.author = author
    book.published_year = book_update.published_year
    book.user = user
    book.genres = genres
    
    await db.commit()
    await db.refresh(book, attribute_names=['author', 'user', 'genres'])
    
    return book

@router.patch('/{book_id}', response_model=booksResponse)
async def update_book_partial(book_id: int, book_update: booksUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(Book.book_id == book_id).options(joinedload(Book.author), selectinload(Book.genres), joinedload(Book.user)))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    updated_data = book_update.model_dump(exclude_unset=True)

    if 'author_id' in updated_data:
        author = await db.execute(select(Author).where(Author.author_id == updated_data['author_id']))
        author = author.scalar_one_or_none()
        if not author:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
        book.author = author

    if 'user_id' in updated_data:
        user = await db.execute(select(User).where(User.user_id == updated_data['user_id']))
        user = user.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        book.user = user

    if 'genre_ids' in updated_data:
        genres = await db.execute(select(Genre).where(Genre.genre_id.in_(updated_data['genre_ids'])))
        genres = genres.scalars().all()
        if len(genres) != len(updated_data['genre_ids']):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
        book.genres = genres
    for key, value in updated_data.items():
        if key not in ['author_id', 'user_id', 'genre_ids']:
            setattr(book, key, value)
    await db.commit()
    await db.refresh(book, attribute_names=['author', 'user', 'genres'])
    return book


@router.delete('/{book_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(Book.book_id == book_id))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    await db.delete(book)
    await db.commit()