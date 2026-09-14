from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from ...image_utils import process_profile_pic, delete_profile_pic
from PIL import UnidentifiedImageError
from typing import Annotated
from ...orm import User, get_db, Book
from ..schema import UserCreate, booksResponse, UserUpdate, publicUserResponse, privateUserResponse, Token
from sqlalchemy.orm import joinedload
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from ..auth import AUTH_COOKIE_NAME, CurrentUser, create_access_token, hash_password, require_owner, verify_password
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
    
    new_user = User(username=user.username, email=user.email.lower(), password_hash=hash_password(user.password))
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user, attribute_names=['username', 'email', 'password_hash', 'image_file'])
    return new_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(func.lower(User.email) == form_data.username.lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(data={"sub": str(user.user_id)}, expires_delta=access_token_expires)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        max_age=int(access_token_expires.total_seconds()),
        samesite="lax",
        secure=False,
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(key=AUTH_COOKIE_NAME, httponly=True, samesite="lax")


@router.get("/me", response_model=privateUserResponse)
async def read_users_me(current_user: CurrentUser):
    return current_user




@router.get("/{user_id}", response_model=privateUserResponse)
async def get_user(user_id: int, current_user: CurrentUser):
    require_owner(user_id, current_user)
    return current_user


@router.get("/{user_id}/books", response_model=list[booksResponse])
async def get_user_books(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_owner(user_id, current_user)
    books = await db.execute(
        select(Book)
        .where(Book.user_id == current_user.user_id)
        .options(joinedload(Book.author), joinedload(Book.genres))
    )
    return books.scalars().unique().all()


@router.patch("/{user_id}", response_model=privateUserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_owner(user_id, current_user)
    user = current_user
    

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
        user.password_hash = hash_password(user_update.password)
    if user_update.image_file is not None:
        user.image_file = user_update.image_file

    await db.commit()
    await db.refresh(user, attribute_names=['username', 'email', 'password_hash', 'image_file'])
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    response: Response,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_owner(user_id, current_user)
    await db.delete(current_user)
    await db.commit()
    response.delete_cookie(key=AUTH_COOKIE_NAME, httponly=True, samesite="lax")


@router.patch("/{user_id}/picture", response_model=privateUserResponse)
async def update_user_picture(
    user_id: int,
    image_file: UploadFile,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_owner(user_id, current_user)

    content = await image_file.read()

    if len(content) > settings.max_profile_pic_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile picture size exceeds the maximum limit of {settings.max_profile_pic_size} bytes"
        )

    try:
        new_file_name = await run_in_threadpool(process_profile_pic, content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file"
        )

    old_file_name = current_user.image_file
    current_user.image_file = new_file_name
    await db.commit()
    await db.refresh(current_user, attribute_names=['image_file'])
    if old_file_name:
        delete_profile_pic(old_file_name)
    return current_user

    