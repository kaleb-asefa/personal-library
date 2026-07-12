from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Annotated
from fastapi.responses import RedirectResponse
from ...orm import User, get_db, Book
from ..schema import UserCreate, booksResponse, UserUpdate, publicUserResponse, privateUserResponse
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func
from ..auth import hash_password, verify_password




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
    
    new_user = User(username=user.username, email=user.email.lower(), password_hash=hash_password(user.password))
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user, attribute_names=['username', 'email', 'password_hash', 'image_file'])
    return new_user


@router.post("/session/login", include_in_schema=False)
async def login_session(
    request: Request,
    email: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(url="/login?error=1", status_code=status.HTTP_303_SEE_OTHER)

    request.session["user_id"] = user.user_id
    request.session["username"] = user.username
    request.session["email"] = user.email
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/session/logout", include_in_schema=False)
async def logout_session(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/signup", include_in_schema=False)
async def signup_session(
    request: Request,
    username: Annotated[str, Form(...)],
    email: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(func.lower(User.username) == username.lower()))
    if result.first():
        return RedirectResponse(url="/users/new?error=username", status_code=status.HTTP_303_SEE_OTHER)

    result = await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    if result.first():
        return RedirectResponse(url="/users/new?error=email", status_code=status.HTTP_303_SEE_OTHER)

    new_user = User(username=username.strip(), email=email.lower().strip(), password_hash=hash_password(password))
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    request.session["user_id"] = new_user.user_id
    request.session["username"] = new_user.username
    request.session["email"] = new_user.email
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)




@router.get("/{user_id}", response_model=publicUserResponse)
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
    
    books = await db.execute(select(Book).where(Book.user_id == user_id).options(joinedload(Book.author), joinedload(Book.genres), joinedload(Book.user)))
    books = books.scalars().unique().all()
    return books

@router.patch("/{user_id}", response_model=privateUserResponse)
async def update_user(user_id: int, user_update: UserUpdate, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    

    if user_update.username and user_update.username.lower() != user.username.lower():
        result = await db.execute(select(User).where(func.lower(User.username) == user_update.username.lower()))
        if result.first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
        
    if user_update.email and user_update.email.lower() != user.email.lower():
        result = await db.execute(select(User).where(func.lower(User.email) == user_update.email.lower()))
        if result.first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
        
    if user_update.username:
        user.username = user_update.username.lower()
    if user_update.email:
        user.email = user_update.email.lower()
    if user_update.password:
        user.password = hash_password(user_update.password)
    if user_update.image_file is not None:
        user.image_file = user_update.image_file

    await db.commit()
    await db.refresh(user, attribute_names=['username', 'email', 'password', 'image_file'])
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    user = await db.execute(select(User).where(User.user_id == user_id))
    user = user.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)
    await db.commit()