from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas.user import AdminLogin, Token

router = APIRouter(prefix="/auth", tags=["admin-auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login", response_model=Token)
async def admin_login(data: AdminLogin):
    with get_db() as db:
        user = db.query(User).filter(User.email == data.email).first()

        if not user or not pwd_context.verify(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="邮箱或密码错误",
            )

        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="仅管理员可登录后台",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账户已被禁用",
            )

        user.last_login_at = datetime.utcnow()
        db.commit()

        expire = datetime.utcnow() + timedelta(days=settings.access_token_expire_days)
        access_token = jwt.encode(
            {"sub": user.id, "exp": expire},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        return Token(access_token=access_token)
