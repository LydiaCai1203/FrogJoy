from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    is_admin: bool = False
    created_at: Optional[datetime] = None


class UserInDB(BaseModel):
    id: str
    email: str
    password_hash: str
    created_at: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


class ThemeIn(BaseModel):
    theme: str


class ThemeOut(BaseModel):
    theme: str


class FontSizeIn(BaseModel):
    font_size: int


class FontSizeOut(BaseModel):
    font_size: int


class VerifyRequest(BaseModel):
    token: str


class ResendRequest(BaseModel):
    email: EmailStr


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class DeviceInfo(BaseModel):
    session_id: str
    device_name: str
    device_type: str
    last_active: str
    is_current: bool = False
