from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Annotated
from ...orm import User, get_db, Book
from ..schema import UserCreate, booksResponse, UserUpdate, publicUserResponse, privateUserResponse
from sqlalchemy.orm import joinedload
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from ..auth import create_access_token, verify_access_token, hash_password, verify_password, oauth2_scheme
from ..config import settings




router = APIRouter()

@router.post("", response_model=privateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(User).where(func.lower(User.username) == user.username.lower()))
    result = result.first()
    if result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    
    result = await db.execute(select(User).where(func.lower(User.email) == user.email.lower()))
    result = result.first()
    if result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
    
    new_user = User(username=user.username, email=user.email, password_hash=hash_password(user.password))
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user, attribute_names=['username', 'email', 'password'])
    return new_user

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.get("/{user_id}/books", response_model=list[booksResponse])
async def get_user_books(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    books = db.execute(select(Book).where(Book.user_id == user_id).options(joinedload(Book.author), joinedload(Book.genres))).scalars().unique().all()
    return books

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_update: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    updated_data = user_update.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user, attribute_names=['username', 'email', 'password'])
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)
    await db.commit()