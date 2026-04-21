import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from shared.redis_client import get_redis

SESSION_PREFIX = "session:"
USER_SESSIONS_PREFIX = "user:sessions:"
SESSION_TTL = 86400 * 30  # 30 days


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_session_id() -> str:
    return str(uuid.uuid4())


def generate_refresh_token(session_id: str) -> str:
    """Generate refresh token with embedded session_id for O(1) lookup."""
    return f"{session_id}:{secrets.token_urlsafe(64)}"


def create_session(
    user_id: str,
    device_name: str = "Unknown",
    device_type: str = "web",
) -> tuple[str, str]:
    """Create a new session in Redis. Returns (session_id, refresh_token)."""
    r = get_redis()
    session_id = generate_session_id()
    refresh_token = generate_refresh_token(session_id)
    now = datetime.now(timezone.utc).isoformat()

    r.hset(f"{SESSION_PREFIX}{session_id}", mapping={
        "user_id": user_id,
        "refresh_hash": _hash_token(refresh_token),
        "device_name": device_name,
        "device_type": device_type,
        "created_at": now,
        "last_active": now,
    })
    r.expire(f"{SESSION_PREFIX}{session_id}", SESSION_TTL)

    r.sadd(f"{USER_SESSIONS_PREFIX}{user_id}", session_id)
    r.expire(f"{USER_SESSIONS_PREFIX}{user_id}", SESSION_TTL)

    return session_id, refresh_token


def get_session(session_id: str) -> Optional[dict]:
    """Get session data from Redis. Returns None if not found."""
    r = get_redis()
    data = r.hgetall(f"{SESSION_PREFIX}{session_id}")
    if not data:
        return None
    return {k.decode(): v.decode() for k, v in data.items()}


def validate_refresh_token(session_id: str, refresh_token: str) -> Optional[dict]:
    """Validate refresh token against session. Returns session data or None."""
    session = get_session(session_id)
    if not session:
        return None
    if session["refresh_hash"] != _hash_token(refresh_token):
        # Possible token theft — delete this session
        delete_session(session["user_id"], session_id)
        return None
    return session


def rotate_refresh_token(session_id: str, new_refresh_token: str) -> None:
    """Update session with new refresh token hash and last_active."""
    r = get_redis()
    key = f"{SESSION_PREFIX}{session_id}"
    r.hset(key, mapping={
        "refresh_hash": _hash_token(new_refresh_token),
        "last_active": datetime.now(timezone.utc).isoformat(),
    })
    r.expire(key, SESSION_TTL)


def delete_session(user_id: str, session_id: str) -> None:
    """Delete a single session."""
    r = get_redis()
    r.delete(f"{SESSION_PREFIX}{session_id}")
    r.srem(f"{USER_SESSIONS_PREFIX}{user_id}", session_id)


def delete_all_sessions(user_id: str) -> None:
    """Delete all sessions for a user."""
    r = get_redis()
    session_ids = r.smembers(f"{USER_SESSIONS_PREFIX}{user_id}")
    for sid in session_ids:
        r.delete(f"{SESSION_PREFIX}{sid.decode()}")
    r.delete(f"{USER_SESSIONS_PREFIX}{user_id}")


def list_sessions(user_id: str) -> list[dict]:
    """List all active sessions for a user."""
    r = get_redis()
    session_ids = r.smembers(f"{USER_SESSIONS_PREFIX}{user_id}")
    sessions = []
    for sid_bytes in session_ids:
        sid = sid_bytes.decode()
        session = get_session(sid)
        if session:
            session["session_id"] = sid
            sessions.append(session)
        else:
            # Stale reference — clean up
            r.srem(f"{USER_SESSIONS_PREFIX}{user_id}", sid)
    return sessions


def count_sessions(user_id: str) -> int:
    """Count active sessions for a user."""
    r = get_redis()
    return r.scard(f"{USER_SESSIONS_PREFIX}{user_id}")
