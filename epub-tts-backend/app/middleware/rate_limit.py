import time
from collections import defaultdict
from fastapi import HTTPException, status
from app.config import settings
from app.models.database import get_db
from app.models.models import User

# {user_id: {action: [timestamp, ...]}}
_call_log: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

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
