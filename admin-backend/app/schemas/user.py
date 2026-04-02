from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserListItem(BaseModel):
    id: str
    email: str
    is_verified: bool
    is_admin: bool
    is_active: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None
    last_active_at: Optional[str] = None
    book_count: int = 0
    total_reading_seconds: int = 0


class UserListResponse(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    page_size: int


class UserDetail(UserListItem):
    highlight_count: int = 0


class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


class UserStats(BaseModel):
    total_books: int
    total_reading_seconds: int
    total_highlights: int
    reading_days: int
    recent_books: list[dict]
