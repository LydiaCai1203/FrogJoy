import time
from collections import defaultdict
from fastapi import HTTPException, Request, status
from app.config import settings
from app.models.database import get_db
from app.models.models import User

# {user_id: {action: [timestamp, ...]}}
_call_log: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

# {ip: [timestamp, ...]}  用于游客 TTS 按 IP 限频
_guest_tts_ip_log: dict[str, list[float]] = defaultdict(list)

# action -> (max_calls, window_seconds)
RATE_LIMITS = {
    "tts_speak": (5, 60),
    "translate": (1, 60),
    "chat": (1, 60),
}

_guest_user_id: str | None = None


def _get_guest_user_id() -> str | None:
    global _guest_user_id
    if _guest_user_id:
        return _guest_user_id
    if not settings.guest_email:
        return None
    with get_db() as db:
        user = db.query(User).filter(User.email == settings.guest_email).first()
        if user:
            _guest_user_id = user.id
    return _guest_user_id


def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP，优先从 X-Forwarded-For 获取（nginx 代理场景）。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_guest_tts_rate_limit(ip: str) -> None:
    """按 IP 检查游客 TTS 请求频率，1 分钟内超过 5 次则抛出 429。"""
    max_calls, window = RATE_LIMITS["tts_speak"]
    now = time.time()
    cutoff = now - window

    _guest_tts_ip_log[ip] = [t for t in _guest_tts_ip_log[ip] if t > cutoff]

    if len(_guest_tts_ip_log[ip]) >= max_calls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求过于频繁，请{window}秒后再试",
        )

    _guest_tts_ip_log[ip].append(now)


def check_guest_rate_limit(user_id: str, action: str) -> None:
    """Check rate limit. Only enforced for the guest account. Raises 429 if exceeded."""
    guest_id = _get_guest_user_id()
    if not guest_id or user_id != guest_id:
        return

    if action not in RATE_LIMITS:
        return

    max_calls, window = RATE_LIMITS[action]
    now = time.time()
    calls = _call_log[user_id][action]

    # Clean old entries
    _call_log[user_id][action] = [t for t in calls if now - t < window]
    calls = _call_log[user_id][action]

    if len(calls) >= max_calls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"操作过于频繁，请{window}秒后再试",
        )

    calls.append(now)


def is_guest_user(user_id: str) -> bool:
    guest_id = _get_guest_user_id()
    return guest_id is not None and user_id == guest_id
