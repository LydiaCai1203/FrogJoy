from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from app.models.user import UserCreate, UserLogin, UserResponse, Token, ThemeIn, ThemeOut, FontSizeIn, FontSizeOut
from app.models.database import get_db
from app.models.models import User, UserThemePreferences
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.middleware.auth import get_current_user
from app.config import settings
from app.services.system_settings import get_system_setting, get_system_setting_bool

router = APIRouter(prefix="/auth", tags=["auth"])


class VerifyRequest(BaseModel):
    token: str


class ResendRequest(BaseModel):
    email: EmailStr


@router.post("/register")
async def register(user_data: UserCreate):
    if not get_system_setting_bool("allow_registration", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="系统暂不开放注册",
        )
    with get_db() as db:
        try:
            existing = db.query(User).filter(User.email == user_data.email).first()
            if existing:
                if not existing.is_verified:
                    # Resend verification for unverified user
                    token = AuthService.create_verification_token(user_data.email)
                    EmailService.send_verification_email(user_data.email, token)
                    return {"message": "验证邮件已重新发送，请查收邮箱"}
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该邮箱已注册"
                )

            user_id = AuthService.generate_user_id()
            password_hash = AuthService.hash_password(user_data.password)

            user = User(
                id=user_id,
                email=user_data.email,
                password_hash=password_hash,
                is_verified=False,
            )
            db.add(user)
            db.commit()

            token = AuthService.create_verification_token(user_data.email)
            EmailService.send_verification_email(user_data.email, token)

            return {"message": "验证邮件已发送，请查收邮箱"}
        except HTTPException:
            raise
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已注册"
            )
        except Exception:
            db.rollback()
            raise


@router.post("/verify")
async def verify_email(data: VerifyRequest):
    email = AuthService.decode_verification_token(data.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证链接已过期或无效"
        )

    with get_db() as db:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        if user.is_verified:
            # Already verified, just return a token
            access_token = AuthService.create_access_token(user.id)
            return Token(access_token=access_token)

        user.is_verified = True
        db.commit()

        access_token = AuthService.create_access_token(user.id)
        return Token(access_token=access_token)


@router.post("/resend-verification")
async def resend_verification(data: ResendRequest):
    with get_db() as db:
        user = db.query(User).filter(User.email == data.email).first()
        if not user:
            # Don't reveal whether email exists
            return {"message": "如果该邮箱已注册，验证邮件将会发送"}
        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已验证"
            )
        token = AuthService.create_verification_token(data.email)
        EmailService.send_verification_email(data.email, token)
        return {"message": "验证邮件已发送，请查收邮箱"}


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin):
    with get_db() as db:
        user = db.query(User).filter(User.email == user_data.email).first()

        if not user or not AuthService.verify_password(user_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="邮箱或密码错误"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被禁用",
            )

        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="请先验证邮箱"
            )

        user.last_login_at = datetime.utcnow()
        db.commit()

        access_token = AuthService.create_access_token(user.id)
        return Token(access_token=access_token)

@router.get("/me", response_model=UserResponse)
async def get_me(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        return UserResponse(
            id=user.id,
            email=user.email,
            is_admin=bool(user.is_admin),
            created_at=user.created_at.isoformat() if user.created_at else None,
        )

@router.get("/theme", response_model=ThemeOut)
async def get_theme(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.query(UserThemePreferences).filter(UserThemePreferences.user_id == user_id).first()
    if not row:
        return ThemeOut(theme=get_system_setting("default_theme", "eye-care"))
    return ThemeOut(theme=row.theme)

@router.put("/theme", response_model=ThemeOut)
async def save_theme(theme_data: ThemeIn, user_id: str = Depends(get_current_user)):
    valid_themes = ["day", "night", "eye-care"]
    if theme_data.theme not in valid_themes:
        raise HTTPException(status_code=400, detail="Invalid theme")
    with get_db() as db:
        existing = db.query(UserThemePreferences).filter(UserThemePreferences.user_id == user_id).first()
        if existing:
            existing.theme = theme_data.theme
        else:
            existing = UserThemePreferences(user_id=user_id, theme=theme_data.theme)
            db.add(existing)
        db.commit()
    return ThemeOut(theme=theme_data.theme)

@router.get("/font-size", response_model=FontSizeOut)
async def get_font_size(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.query(UserThemePreferences).filter(UserThemePreferences.user_id == user_id).first()
    if not row or row.font_size is None:
        from app.services.system_settings import get_system_setting_int
        return FontSizeOut(font_size=get_system_setting_int("default_font_size", 18))
    return FontSizeOut(font_size=row.font_size)

@router.put("/font-size", response_model=FontSizeOut)
async def save_font_size(font_size_data: FontSizeIn, user_id: str = Depends(get_current_user)):
    font_size = font_size_data.font_size
    if font_size < 12 or font_size > 32:
        raise HTTPException(status_code=400, detail="Font size must be between 12 and 32")
    with get_db() as db:
        existing = db.query(UserThemePreferences).filter(UserThemePreferences.user_id == user_id).first()
        if existing:
            existing.font_size = font_size
        else:
            existing = UserThemePreferences(user_id=user_id, font_size=font_size)
            db.add(existing)
        db.commit()
    return FontSizeOut(font_size=font_size)


@router.get("/guest-token")
async def get_guest_token():
    if not settings.guest_email:
        raise HTTPException(status_code=404, detail="Guest account not configured")
    with get_db() as db:
        user = db.query(User).filter(User.email == settings.guest_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="Guest account not found")
        access_token = AuthService.create_access_token(user.id)
        return Token(access_token=access_token)
