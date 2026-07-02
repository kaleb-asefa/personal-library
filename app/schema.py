from pydantic import BaseModel, Field, ConfigDict, EmailStr

class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    username: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field( max_length=255)
    password: str = Field(min_length=1, max_length=255)

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    user_id: int


class authors(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    author_id: int
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=1, max_length=255)

class Genres(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    genre_id: int
    name: str = Field(min_length=1, max_length=255)

class booksResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    book_id: int
    title: str = Field(min_length=1, max_length=255)
    author: authors  # Nested Pydantic model for author
    published_year: int = Field(ge=0, le=9999)  # Assuming a reasonable range for published year
    status: str = Field(pattern='^(read|unread)$')  # Status can be either 'read' or 'unread'
    genres: list[Genres] = Field(default_factory=list)  # List of genres associated with the book
    rating: float = Field(ge=0, le=5)  # Rating between 0 and 5