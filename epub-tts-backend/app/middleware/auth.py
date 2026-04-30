from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
from app.services import session_service
from app.middleware.rate_limit import get_client_ip
from shared.redis_client import get_redis
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


def _check_session(result: dict, request: Request) -> None:
    """Validate that the Redis session still exists; raise 401 if revoked."""
    session_id = result.get("session_id")
    if not session_id:
        return
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session_service.touch_session(session_id, get_client_ip(request))


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    token = credentials.credentials
    result = AuthService.decode_token(token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _track_active(result["user_id"])
    _check_session(result, request)
    return result["user_id"]


async def get_current_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Returns {"user_id": ..., "session_id": ...}. Use when session_id is needed."""
    token = credentials.credentials
    result = AuthService.decode_token(token)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _track_active(result["user_id"])
    _check_session(result, request)
    return result


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)
) -> str | None:
    if not credentials:
        return None

    try:
        token = credentials.credentials
        result = AuthService.decode_token(token)
        return result["user_id"] if result else None
    except Exception:
        return None


async def get_admin_user(
    user_id: str = Depends(get_current_user)
) -> str:
    from shared.database import get_db
    from shared.models import User

    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
    return user_id
