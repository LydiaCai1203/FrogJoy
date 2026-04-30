from pydantic import BaseModel, EmailStr, Field
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
    name: Optional[str] = None
    is_admin: bool = False
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None


class ProfileUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


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
    last_ip: Optional[str] = None
    is_current: bool = False
