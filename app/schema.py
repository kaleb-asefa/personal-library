from pydantic import BaseModel, Field, ConfigDict, EmailStr

class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field( max_length=255)

class UserCreate(UserBase):
    password: str | None = None

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    image_file: str | None = None
    image_path: str | None = None  # This will be computed based on the image_file

class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = None
    image_file: str | None = None


class authors(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    author_id: int
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=1, max_length=255)

class Genres(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    genre_id: int
    name: str = Field(min_length=1, max_length=255)

class booksBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    book_id: int
    title: str = Field(min_length=1, max_length=255)
    author: authors  # Nested Pydantic model for author
    user_id: int

class booksResponse(booksBase):
    published_year: int
    status: str = Field(min_length=1, max_length=255)
    rating: int = Field(ge=0, le=5)
    genres: list[Genres]  # List of nested Pydantic models for genres

class booksCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    author_id: int
    published_year: int
    user_id: int
    genre_ids: list[int]  # List of genre IDs to associate with the book

class booksUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    author_id: int | None = None
    published_year: int | None = None
    status: str | None = Field(default=None, min_length=1, max_length=255)
    rating: int | None = Field(default=None, ge=0, le=5)
    genre_ids: list[int] | None = None  # List of genre IDs to associate with the book
