from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, status, UploadFile, BackgroundTasks
from starlette.concurrency import run_in_threadpool
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from image_utils import process_profile_pic, delete_profile_pic
from PIL import UnidentifiedImageError
from typing import Annotated
from ..db import get_db
from ..models import User, Book, PasswordResetToken
from ..schema import UserCreate, booksResponse, UserUpdate, publicUserResponse, privateUserResponse, Token, paginatedBooksResponse, ResetPasswordRequest, ChangePasswordRequest, ForgotPasswordRequest
from sqlalchemy.orm import joinedload, selectinload
from datetime import timedelta, datetime, UTC
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from ..auth import AUTH_COOKIE_NAME, CurrentUser, create_access_token, hash_password, require_owner, verify_password, generate_secure_token, hash_reset_token
from ..config import settings
from email_utils import send_password_reset_email
api_router = APIRouter(prefix="/api/users")

@api_router.post("", response_model=privateUserResponse, status_code=status.HTTP_201_CREATED)
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


@api_router.post("/token", response_model=Token)
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


@api_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(key=AUTH_COOKIE_NAME, httponly=True, samesite="lax")


@api_router.get("/me", response_model=privateUserResponse)
async def read_users_me(current_user: CurrentUser):
    return current_user


@api_router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(User).where(func.lower(User.email) == request.email.lower()))
    user = result.scalar_one_or_none()

    if user:
        await db.execute(
            sql_delete(PasswordResetToken).where(PasswordResetToken.user_id == user.user_id))

        token = generate_secure_token()
        token_hash = hash_reset_token(token)
        expires_at = datetime.now(UTC) + timedelta(minutes=settings.reset_password_token_expire_minutes)

        password_reset_token = PasswordResetToken(
            user_id=user.user_id,
            token=token_hash,
            expires_at=expires_at,
        )
        db.add(password_reset_token)
        await db.commit()
        background_tasks.add_task(send_password_reset_email, user.email, user.username, token)

    return {"message": "If an account with that email exists, a password reset email has been sent."}


@api_router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(request.token)))
    token_entry = result.scalar_one_or_none()

    if not token_entry or token_entry.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.user_id == token_entry.user_id))
    user = result.scalar_one()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired token")

    user.password_hash = hash_password(request.new_password)
    await db.execute(sql_delete(PasswordResetToken).where(PasswordResetToken.user_id == user.user_id))
    await db.commit()

    return {"message": "Password has been reset successfully. you can now log in with your new password."}


@api_router.patch("/me/password", status_code=status.HTTP_200_OK)
async def update_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.password_hash = hash_password(request.new_password)
    await db.execute(sql_delete(PasswordResetToken).where(PasswordResetToken.user_id == current_user.user_id))
    await db.commit()

    return {"message": "Password has been updated successfully."}


@api_router.get("/{user_id}", response_model=privateUserResponse)
async def get_user(user_id: int, current_user: CurrentUser):
    require_owner(user_id, current_user)
    return current_user


@api_router.get("/{user_id}/books", response_model=paginatedBooksResponse)
async def get_user_books(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    require_owner(user_id, current_user)
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
        .options(joinedload(Book.author), selectinload(Book.genres))
    )
    books = books.scalars().unique().all()

    return paginatedBooksResponse(
        books=books,
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + len(books) < total,
    )


@api_router.patch("/{user_id}", response_model=privateUserResponse)
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

    await db.commit()
    await db.refresh(user, attribute_names=['username', 'email', 'password_hash', 'image_file'])
    return user

@api_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@api_router.patch("/{user_id}/picture", response_model=privateUserResponse)
async def update_user_picture(
    user_id: int,
    image_file: Annotated[UploadFile, File()],
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

@api_router.delete("/{user_id}/picture", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_picture(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_owner(user_id, current_user)
    old_file_name = current_user.image_file
    if old_file_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete"
        )
    current_user.image_file = None

    await db.commit()
    await db.refresh(current_user, attribute_names=['image_file'])
    delete_profile_pic(old_file_name)
    return current_user


router = api_router
    