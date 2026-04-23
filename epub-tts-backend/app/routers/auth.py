import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Request, UploadFile, File
from sqlalchemy.exc import IntegrityError
from user_agents import parse as parse_ua
from shared.schemas.auth import (
    UserCreate, UserResponse, TokenPair,
    ThemeIn, ThemeOut, FontSizeIn, FontSizeOut,
    VerifyRequest, ResendRequest, RefreshRequest, LoginRequest, DeviceInfo,
    ProfileUpdate,
)
from shared.models import User, UserPreferences
from shared.database import get_db
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services import session_service
from app.middleware.auth import get_current_user, get_current_session
from shared.config import settings
from app.services.system_settings import get_system_setting, get_system_setting_bool
from app.middleware.rate_limit import is_guest_user
from typing import List

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_DEVICES = 3


def _parse_device_info(request: Request) -> tuple[str, str]:
    """Parse User-Agent header into (device_name, device_type)."""
    ua_string = request.headers.get("user-agent", "")
    try:
        ua = parse_ua(ua_string)
        os_name = ua.os.family or "Unknown"
        browser_name = ua.browser.family or "Unknown"
        device_name = f"{os_name} - {browser_name}"
        if ua.is_mobile:
            device_type = "mobile"
        elif ua.is_tablet:
            device_type = "tablet"
        else:
            device_type = "web"
    except Exception:
        device_name = "Unknown"
        device_type = "web"
    return device_name, device_type


def _create_token_pair(user_id: str, device_name: str = "Unknown", device_type: str = "web") -> dict:
    """Create a session and return access + refresh tokens."""
    session_id, refresh_token = session_service.create_session(
        user_id=user_id,
        device_name=device_name,
        device_type=device_type,
    )
    access_token = AuthService.create_access_token(user_id, session_id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/register")
async def register(user_data: UserCreate):
    if not get_system_setting_bool("allow_registration", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="系统暂不开放注册",
        )
    with get_db() as db:
        try:
            smtp_available = bool(settings.smtp_host and settings.smtp_user)

            existing = db.query(User).filter(User.email == user_data.email).first()
            if existing:
                if not existing.is_verified:
                    if smtp_available:
                        token = AuthService.create_verification_token(user_data.email)
                        EmailService.send_verification_email(user_data.email, token)
                        return {"message": "验证邮件已重新发送，请查收邮箱"}
                    else:
                        existing.is_verified = True
                        db.commit()
                        return TokenPair(**_create_token_pair(existing.id))
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
                is_verified=not smtp_available,
            )
            db.add(user)
            db.commit()

            if smtp_available:
                token = AuthService.create_verification_token(user_data.email)
                EmailService.send_verification_email(user_data.email, token)
                return {"message": "验证邮件已发送，请查收邮箱"}
            else:
                return TokenPair(**_create_token_pair(user_id))
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
        if not user.is_verified:
            user.is_verified = True
            db.commit()

        return TokenPair(**_create_token_pair(user.id))


@router.post("/resend-verification")
async def resend_verification(data: ResendRequest):
    with get_db() as db:
        user = db.query(User).filter(User.email == data.email).first()
        if not user:
            return {"message": "如果该邮箱已注册，验证邮件将会发送"}
        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该邮箱已验证"
            )
        token = AuthService.create_verification_token(data.email)
        EmailService.send_verification_email(data.email, token)
        return {"message": "验证邮件已发送，请查收邮箱"}


@router.post("/login", response_model=TokenPair)
async def login(user_data: LoginRequest, request: Request):
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

        # Check device limit (skip for guest)
        if not is_guest_user(user.id):
            current_count = session_service.count_sessions(user.id)
            if current_count >= MAX_DEVICES:
                devices = session_service.list_sessions(user.id)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": f"已达最大设备数({MAX_DEVICES})，请先退出其他设备",
                        "devices": [
                            {
                                "session_id": s["session_id"],
                                "device_name": s.get("device_name", "Unknown"),
                                "device_type": s.get("device_type", "web"),
                                "last_active": s.get("last_active", ""),
                            }
                            for s in devices
                        ],
                    },
                )

        user.last_login_at = datetime.utcnow()
        db.commit()

        device_name, device_type = _parse_device_info(request)
        return TokenPair(**_create_token_pair(
            user.id,
            device_name=device_name,
            device_type=device_type,
        ))


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(data: RefreshRequest):
    """Refresh access token using a valid refresh token."""
    # Refresh token format: "session_id:random_part"
    parts = data.refresh_token.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    session_id, _ = parts
    session = session_service.validate_refresh_token(session_id, data.refresh_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Rotate refresh token
    new_refresh_token = session_service.generate_refresh_token(session_id)
    session_service.rotate_refresh_token(session_id, new_refresh_token)

    access_token = AuthService.create_access_token(session["user_id"], session_id)
    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout")
async def logout(session_info: dict = Depends(get_current_session)):
    """Logout current device — delete the session from Redis."""
    session_service.delete_session(session_info["user_id"], session_info["session_id"])
    return {"message": "已退出登录"}


@router.post("/logout-all")
async def logout_all(user_id: str = Depends(get_current_user)):
    """Logout all devices — delete all sessions for the user."""
    session_service.delete_all_sessions(user_id)
    return {"message": "已退出所有设备"}


@router.get("/devices", response_model=List[DeviceInfo])
async def list_devices(session_info: dict = Depends(get_current_session)):
    """List all active devices/sessions for the current user."""
    sessions = session_service.list_sessions(session_info["user_id"])
    return [
        DeviceInfo(
            session_id=s["session_id"],
            device_name=s.get("device_name", "Unknown"),
            device_type=s.get("device_type", "web"),
            last_active=s.get("last_active", ""),
            is_current=(s["session_id"] == session_info["session_id"]),
        )
        for s in sessions
    ]


@router.delete("/devices/{session_id}")
async def remove_device(session_id: str, session_info: dict = Depends(get_current_session)):
    """Kick a specific device. Cannot kick your own session."""
    if session_id == session_info["session_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能踢出当前设备，请使用退出登录",
        )

    # Verify the session belongs to the current user
    target_session = session_service.get_session(session_id)
    if not target_session or target_session["user_id"] != session_info["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="设备不存在",
        )

    session_service.delete_session(session_info["user_id"], session_id)
    return {"message": "设备已退出"}


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
            name=user.name,
            is_admin=bool(user.is_admin),
            avatar_url=user.avatar_url,
            created_at=user.created_at.isoformat() if user.created_at else None,
        )


@router.put("/profile", response_model=UserResponse)
async def update_profile(data: ProfileUpdate, user_id: str = Depends(get_current_user)):
    if is_guest_user(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="游客账户不支持此操作",
        )
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user.name = data.name.strip() or None
        db.commit()
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_admin=bool(user.is_admin),
            avatar_url=user.avatar_url,
            created_at=user.created_at.isoformat() if user.created_at else None,
        )


ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
AVATAR_MAX_SIZE = 2 * 1024 * 1024  # 2MB
MIME_TO_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...), user_id: str = Depends(get_current_user)):
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPEG、PNG、WebP 格式")

    data = await file.read()
    if len(data) > AVATAR_MAX_SIZE:
        raise HTTPException(status_code=400, detail="头像文件不能超过 2MB")

    ext = MIME_TO_EXT[file.content_type]
    avatar_dir = os.path.join(settings.data_dir, "users", user_id)
    os.makedirs(avatar_dir, exist_ok=True)

    # Remove old avatar files
    for old in os.listdir(avatar_dir):
        if old.startswith("avatar."):
            os.remove(os.path.join(avatar_dir, old))

    avatar_path = os.path.join(avatar_dir, f"avatar.{ext}")
    with open(avatar_path, "wb") as f:
        f.write(data)

    avatar_url = f"/api/files/avatar/{user_id}"
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.avatar_url = avatar_url
            db.commit()

    return {"avatar_url": avatar_url}


@router.get("/theme", response_model=ThemeOut)
async def get_theme(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not row:
        return ThemeOut(theme=get_system_setting("default_theme", "eye-care"))
    return ThemeOut(theme=row.theme)


@router.put("/theme", response_model=ThemeOut)
async def save_theme(theme_data: ThemeIn, user_id: str = Depends(get_current_user)):
    valid_themes = ["day", "night", "eye-care"]
    if theme_data.theme not in valid_themes:
        raise HTTPException(status_code=400, detail="Invalid theme")
    with get_db() as db:
        existing = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if existing:
            existing.theme = theme_data.theme
        else:
            existing = UserPreferences(user_id=user_id, theme=theme_data.theme)
            db.add(existing)
        db.commit()
    return ThemeOut(theme=theme_data.theme)


@router.get("/font-size", response_model=FontSizeOut)
async def get_font_size(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
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
        existing = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if existing:
            existing.font_size = font_size
        else:
            existing = UserPreferences(user_id=user_id, font_size=font_size)
            db.add(existing)
        db.commit()
    return FontSizeOut(font_size=font_size)


@router.get("/guest-token", response_model=TokenPair)
async def get_guest_token(request: Request):
    if not settings.guest_email:
        raise HTTPException(status_code=404, detail="Guest account not configured")
    with get_db() as db:
        user = db.query(User).filter(User.email == settings.guest_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="Guest account not found")
        device_name, device_type = _parse_device_info(request)
        return TokenPair(**_create_token_pair(
            user.id,
            device_name=device_name,
            device_type=device_type,
        ))
