from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from app.redis_client import get_redis
from typing import Optional

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

ACTIVE_KEY_PREFIX = "user:last_active:"
ACTIVE_TTL = 86400 * 30  # 30 days


def _track_active(user_id: str) -> None:
    """Record user activity timestamp in Redis. Fire-and-forget."""
    try:
        r = get_redis()
        r.set(f"{ACTIVE_KEY_PREFIX}{user_id}", datetime.now(timezone.utc).isoformat(), ex=ACTIVE_TTL)
    except Exception:
        pass  # Redis down should not break the app


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    token = credentials.credentials
    user_id = AuthService.decode_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _track_active(user_id)
    return user_id

async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)
) -> str | None:
    if not credentials:
        return None

    try:
        token = credentials.credentials
        return AuthService.decode_token(token)
    except Exception:
        return None


async def get_admin_user(
    user_id: str = Depends(get_current_user)
) -> str:
    from app.models.database import get_db
    from app.models.models import User

    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
    return user_id
