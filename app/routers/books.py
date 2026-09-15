from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import Annotated
from ...orm import Book, get_db, Author, Genre
from ..schema import booksResponse, booksCreate, booksUpdate, paginatedBooksResponse
from sqlalchemy.orm import joinedload, selectinload
from ..auth import CurrentUser, require_owner

router = APIRouter()


@router.get('', response_model=paginatedBooksResponse)
async def api_books(current_user: CurrentUser, db : Annotated[AsyncSession, Depends(get_db)],
                    skip: int = Query(0, ge=0),
                    limit: int = Query(10, ge=1, le=100)):


    total = await db.execute(
        select(func.count(Book.book_id))
        .where(Book.user_id == current_user.user_id)
    )
    total = total.scalar_one() or 0

    books = await db.execute(
        select(Book)
        .where(Book.user_id == current_user.user_id)
        .order_by(Book.published_year.desc())
        .offset(skip)
        .limit(limit)
        .options(joinedload(Book.author), selectinload(Book.genres), joinedload(Book.user))
    )
    books = books.scalars().unique().all()

    has_more = skip + len(books) < total

    return paginatedBooksResponse(
        books=books,
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more
    )

@router.post('', response_model=booksResponse, status_code=status.HTTP_201_CREATED)
async def api_create_book(book: booksCreate, db: Annotated[AsyncSession, Depends(get_db)], current_user: CurrentUser):
    author = await db.execute(select(Author).where(Author.name == book.author_name))
    author = author.scalar_one_or_none()
    if not author:
        author = Author(name=book.author_name)
        db.add(author)

    
    genre_result = await db.execute(select(Genre).where(Genre.name.in_(book.genre_names)))
    genres = list(genre_result.scalars().all())
    existing_genre_names = {genre.name for genre in genres}
    new_genres = [Genre(name=name) for name in book.genre_names if name not in existing_genre_names]
    db.add_all(new_genres)
    genres.extend(new_genres)
    
    new_book = Book(
        title=book.title,
        author=author,
        user=current_user,
        published_year=book.published_year,
        status='unread',
        rating=0,
        genres=genres
    )
    
    db.add(new_book)
    await db.commit()
    await db.refresh(new_book, attribute_names=['author', 'user', 'genres'])
    
    return new_book

@router.get('/{book_id}', response_model=booksResponse)
async def api_book_detail(book_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    book = await db.execute(select(Book).where(
        Book.book_id == book_id).options(
            joinedload(Book.author), 
            selectinload(Book.genres),
            joinedload(Book.user)))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    require_owner(book.user_id, current_user)
    return book

@router.put('/{book_id}', response_model=booksResponse)
async def update_book_full(
    book_id: int,
    book_update: booksCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    book = await db.execute(select(Book).where(Book.book_id == book_id))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    require_owner(book.user_id, current_user)

    author = await db.execute(select(Author).where(Author.name == book_update.author_name))
    author = author.scalar_one_or_none()
    if not author:
        author = Author(name=book_update.author_name)
        db.add(author)

    genre_result = await db.execute(select(Genre).where(Genre.name.in_(book_update.genre_names)))
    genres = list(genre_result.scalars().all())
    existing_genre_names = {genre.name for genre in genres}
    new_genres = [Genre(name=name) for name in book_update.genre_names if name not in existing_genre_names]
    db.add_all(new_genres)
    genres.extend(new_genres)
    
    book.title = book_update.title
    book.author = author
    book.published_year = book_update.published_year
    book.genres = genres
    
    await db.commit()
    await db.refresh(book, attribute_names=['author', 'user', 'genres'])
    
    return book

@router.patch('/{book_id}', response_model=booksResponse)
async def update_book_partial(
    book_id: int,
    book_update: booksUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    book = await db.execute(select(Book).where(Book.book_id == book_id).options(joinedload(Book.author), selectinload(Book.genres), joinedload(Book.user)))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    require_owner(book.user_id, current_user)
    updated_data = book_update.model_dump(exclude_unset=True)

    if 'author_id' in updated_data:
        author = await db.execute(select(Author).where(Author.author_id == updated_data['author_id']))
        author = author.scalar_one_or_none()
        if not author:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Author not found")
        book.author = author

    if 'genre_ids' in updated_data:
        genres = await db.execute(select(Genre).where(Genre.genre_id.in_(updated_data['genre_ids'])))
        genres = genres.scalars().all()
        if len(genres) != len(updated_data['genre_ids']):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more genres not found")
        book.genres = genres
    for key, value in updated_data.items():
        if key not in ['author_id', 'genre_ids']:
            setattr(book, key, value)
    await db.commit()
    await db.refresh(book, attribute_names=['author', 'user', 'genres'])
    return book

@router.delete('/{book_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(
    book_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    book = await db.execute(select(Book).where(Book.book_id == book_id))
    book = book.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    require_owner(book.user_id, current_user)
    await db.delete(book)
    await db.commit()