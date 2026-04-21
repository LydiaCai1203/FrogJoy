# Multi-Device Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add refresh token mechanism, Redis session management, device management (list/kick/logout-all), and max 3 device limit to BookReader's auth system.

**Architecture:** Stateless JWT access tokens (24h) + opaque refresh tokens (30d) stored as SHA-256 hashes in Redis. Each login creates a session in Redis with device metadata. Frontend intercepts 401s to auto-refresh, with concurrency deduplication.

**Tech Stack:** Python/FastAPI (backend), Redis (sessions), React/TypeScript (frontend), python-jose, secrets, hashlib

---

## File Structure

### Backend — New Files
- `epub-tts-backend/app/services/session_service.py` — Redis session CRUD (create, get, delete, list, refresh, logout-all)

### Backend — Modified Files
- `epub-tts-backend/app/services/auth_service.py` — Add refresh token generation, add `sid` to JWT payload, change expiry to 24h
- `epub-tts-backend/shared/schemas/auth.py` — New schemas: `TokenPair`, `RefreshRequest`, `DeviceInfo`, `LoginRequest`
- `epub-tts-backend/app/routers/auth.py` — Modify login/guest-token, add refresh/logout/devices/logout-all endpoints
- `epub-tts-backend/app/middleware/auth.py` — Extract `sid` from JWT for device identification

### Frontend — Modified Files
- `epub-tts-frontend/src/contexts/AuthContext.tsx` — Dual token storage, refresh logic, logout calls backend
- `epub-tts-frontend/src/api/services.ts` — `getEffectiveToken()` reads new storage key

---

### Task 1: Session Service — Redis Session CRUD

**Files:**
- Create: `epub-tts-backend/app/services/session_service.py`

- [ ] **Step 1: Create session_service.py with all session operations**

Refresh tokens use the format `"session_id:random_part"` so the `/auth/refresh` endpoint can extract the session_id for O(1) lookup without scanning all sessions.

```python
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
```

- [ ] **Step 2: Verify the file is syntactically correct**

Run: `cd /Users/caiqj/project/private/BookReader && python -c "import ast; ast.parse(open('epub-tts-backend/app/services/session_service.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add epub-tts-backend/app/services/session_service.py
git commit -m "feat(auth): add Redis session service for multi-device support"
```

---

### Task 2: Update AuthService — Refresh Token + Session-Aware JWT

**Files:**
- Modify: `epub-tts-backend/app/services/auth_service.py`

- [ ] **Step 1: Update auth_service.py**

Replace the `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_DAYS`, `create_access_token`, and `decode_token` sections. Keep everything else (password hashing, verification tokens, encryption) unchanged.

Change the top-level constants:

```python
# Old:
SECRET_KEY = "your-secret-key-change-in-production"  # TODO: 从环境变量读取
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
```

Replace with:

```python
import os

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
```

Update `create_access_token` to accept `session_id` and use hours:

```python
    @staticmethod
    def create_access_token(user_id: str, session_id: str = "") -> str:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        to_encode = {
            "sub": user_id,
            "sid": session_id,
            "exp": expire,
        }
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
```

Update `decode_token` to return both user_id and session_id:

```python
    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode JWT token. Returns {"user_id": ..., "session_id": ...} or None."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("sub")
            session_id: str = payload.get("sid", "")
            if not user_id:
                return None
            return {"user_id": user_id, "session_id": session_id}
        except JWTError:
            return None
```

- [ ] **Step 2: Verify syntax**

Run: `cd /Users/caiqj/project/private/BookReader && python -c "import ast; ast.parse(open('epub-tts-backend/app/services/auth_service.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add epub-tts-backend/app/services/auth_service.py
git commit -m "feat(auth): session-aware JWT with 24h expiry and env-based secret"
```

---

### Task 3: Update Auth Middleware — Handle New decode_token Return Type

**Files:**
- Modify: `epub-tts-backend/app/middleware/auth.py`

- [ ] **Step 1: Update get_current_user to handle dict return from decode_token**

Replace the entire file content with:

```python
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService
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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
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
    return result["user_id"]


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security)
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
```

- [ ] **Step 2: Verify syntax**

Run: `cd /Users/caiqj/project/private/BookReader && python -c "import ast; ast.parse(open('epub-tts-backend/app/middleware/auth.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add epub-tts-backend/app/middleware/auth.py
git commit -m "feat(auth): middleware returns session info, add get_current_session"
```

---

### Task 4: Update Schemas — New Request/Response Models

**Files:**
- Modify: `epub-tts-backend/shared/schemas/auth.py`

- [ ] **Step 1: Add new schemas to auth.py**

Append the following after the existing `ResendRequest` class (keep all existing schemas unchanged):

```python
class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: Optional[str] = None
    device_type: Optional[str] = "web"


class DeviceInfo(BaseModel):
    session_id: str
    device_name: str
    device_type: str
    last_active: str
    is_current: bool = False
```

- [ ] **Step 2: Verify syntax**

Run: `cd /Users/caiqj/project/private/BookReader && python -c "import ast; ast.parse(open('epub-tts-backend/shared/schemas/auth.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add epub-tts-backend/shared/schemas/auth.py
git commit -m "feat(auth): add TokenPair, RefreshRequest, LoginRequest, DeviceInfo schemas"
```

---

### Task 5: Update Auth Router — Login, Logout, Refresh, Devices

**Files:**
- Modify: `epub-tts-backend/app/routers/auth.py`

This is the largest change. Replace the entire file content.

- [ ] **Step 1: Rewrite auth.py router**

Replace the full file with:

```python
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.exc import IntegrityError
from shared.schemas.auth import (
    UserCreate, UserLogin, UserResponse, Token, TokenPair,
    ThemeIn, ThemeOut, FontSizeIn, FontSizeOut,
    VerifyRequest, ResendRequest, RefreshRequest, LoginRequest, DeviceInfo,
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
async def login(user_data: LoginRequest):
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

        return TokenPair(**_create_token_pair(
            user.id,
            device_name=user_data.device_name or "Unknown",
            device_type=user_data.device_type or "web",
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
            is_admin=bool(user.is_admin),
            created_at=user.created_at.isoformat() if user.created_at else None,
        )


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
async def get_guest_token():
    if not settings.guest_email:
        raise HTTPException(status_code=404, detail="Guest account not configured")
    with get_db() as db:
        user = db.query(User).filter(User.email == settings.guest_email).first()
        if not user:
            raise HTTPException(status_code=404, detail="Guest account not found")
        return TokenPair(**_create_token_pair(
            user.id,
            device_name="Guest",
            device_type="web",
        ))


```

- [ ] **Step 2: Verify syntax**

Run: `cd /Users/caiqj/project/private/BookReader && python -c "import ast; ast.parse(open('epub-tts-backend/app/routers/auth.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add epub-tts-backend/app/routers/auth.py
git commit -m "feat(auth): login with sessions, refresh/logout/devices endpoints"
```

---

### Task 6: Update Frontend — AuthContext with Refresh Logic

**Files:**
- Modify: `epub-tts-frontend/src/contexts/AuthContext.tsx`

- [ ] **Step 1: Rewrite AuthContext.tsx**

Replace the entire file with:

```tsx
import { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import type { ReactNode } from "react";
import { API_URL } from "@/config";

interface User {
  id: string;
  email: string;
  is_admin?: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isGuest: boolean;
  isLoading: boolean;
  login: (email: string, password: string, deviceName?: string, deviceType?: string) => Promise<void>;
  register: (email: string, password: string) => Promise<string>;
  verifyEmail: (token: string) => Promise<void>;
  resendVerification: (email: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function saveTokens(access: string, refresh: string, prefix: "auth" | "guest") {
  localStorage.setItem(`${prefix}_access_token`, access);
  localStorage.setItem(`${prefix}_refresh_token`, refresh);
}

function clearTokens(prefix: "auth" | "guest") {
  localStorage.removeItem(`${prefix}_access_token`);
  localStorage.removeItem(`${prefix}_refresh_token`);
}

function getTokens(prefix: "auth" | "guest") {
  return {
    access: localStorage.getItem(`${prefix}_access_token`),
    refresh: localStorage.getItem(`${prefix}_refresh_token`),
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [guestAccessToken, setGuestAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Refresh deduplication
  const refreshPromiseRef = useRef<Promise<string | null> | null>(null);

  const refreshAccessToken = useCallback(async (prefix: "auth" | "guest"): Promise<string | null> => {
    // Deduplicate concurrent refresh calls
    if (refreshPromiseRef.current) {
      return refreshPromiseRef.current;
    }

    const promise = (async () => {
      const { refresh } = getTokens(prefix);
      if (!refresh) return null;

      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });

        if (!res.ok) {
          clearTokens(prefix);
          return null;
        }

        const data = await res.json();
        saveTokens(data.access_token, data.refresh_token, prefix);

        if (prefix === "auth") {
          setAccessToken(data.access_token);
        } else {
          setGuestAccessToken(data.access_token);
        }

        return data.access_token as string;
      } catch {
        clearTokens(prefix);
        return null;
      } finally {
        refreshPromiseRef.current = null;
      }
    })();

    refreshPromiseRef.current = promise;
    return promise;
  }, []);

  useEffect(() => {
    const { access: savedToken } = getTokens("auth");
    if (savedToken) {
      setAccessToken(savedToken);
      fetchUser(savedToken);
    } else {
      fetchGuestToken();
    }
  }, []);

  const fetchGuestToken = async () => {
    try {
      const res = await fetch(`${API_URL}/auth/guest-token`);
      if (res.ok) {
        const data = await res.json();
        setGuestAccessToken(data.access_token);
        saveTokens(data.access_token, data.refresh_token, "guest");
      }
    } catch {
      // Guest token not available
    } finally {
      setIsLoading(false);
    }
  };

  const fetchUser = async (authToken: string) => {
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const userData = await res.json();
        setUser(userData);
      } else if (res.status === 401) {
        // Try refresh
        const newToken = await refreshAccessToken("auth");
        if (newToken) {
          const retryRes = await fetch(`${API_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${newToken}` },
          });
          if (retryRes.ok) {
            setUser(await retryRes.json());
            return;
          }
        }
        clearTokens("auth");
        setAccessToken(null);
        await fetchGuestToken();
      } else {
        clearTokens("auth");
        setAccessToken(null);
        await fetchGuestToken();
      }
    } catch {
      clearTokens("auth");
      setAccessToken(null);
      await fetchGuestToken();
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string, deviceName?: string, deviceType?: string) => {
    const res = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        device_name: deviceName || navigator.userAgent.slice(0, 50),
        device_type: deviceType || "web",
      }),
    });

    if (!res.ok) {
      const error = await res.json();
      // Handle 409 (max devices) — error.detail is an object
      if (res.status === 409 && typeof error.detail === "object") {
        throw new Error(error.detail.message || "已达最大设备数");
      }
      throw new Error(typeof error.detail === "string" ? error.detail : "Login failed");
    }

    const data = await res.json();
    setAccessToken(data.access_token);
    setGuestAccessToken(null);
    saveTokens(data.access_token, data.refresh_token, "auth");
    clearTokens("guest");
    setUser({ id: "", email });
    await fetchUser(data.access_token);

    const themeRes = await fetch(`${API_URL}/auth/theme`, {
      headers: { Authorization: `Bearer ${data.access_token}` },
    });
    if (themeRes.ok) {
      const themeData = await themeRes.json();
      localStorage.setItem("bookreader-theme-logged-in", themeData.theme);
    }
  };

  const register = async (email: string, password: string): Promise<string> => {
    const res = await fetch(`${API_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Registration failed");
    }

    if (data.access_token) {
      setAccessToken(data.access_token);
      setGuestAccessToken(null);
      saveTokens(data.access_token, data.refresh_token, "auth");
      clearTokens("guest");
      await fetchUser(data.access_token);
      return "__auto_login__";
    }

    return data.message;
  };

  const verifyEmail = async (verifyToken: string) => {
    const res = await fetch(`${API_URL}/auth/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: verifyToken }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Verification failed");
    }

    setAccessToken(data.access_token);
    setGuestAccessToken(null);
    saveTokens(data.access_token, data.refresh_token, "auth");
    clearTokens("guest");
    await fetchUser(data.access_token);
  };

  const resendVerification = async (email: string) => {
    const res = await fetch(`${API_URL}/auth/resend-verification`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to resend");
    }
  };

  const logout = async () => {
    // Call backend to invalidate session
    const currentToken = accessToken;
    if (currentToken) {
      try {
        await fetch(`${API_URL}/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${currentToken}` },
        });
      } catch {
        // Best-effort
      }
    }
    setUser(null);
    setAccessToken(null);
    clearTokens("auth");
    fetchGuestToken();
  };

  // Effective token: prefer user token, fallback to guest token
  const effectiveToken = accessToken || guestAccessToken;
  const isGuest = !accessToken && !!guestAccessToken;

  return (
    <AuthContext.Provider value={{ user, token: effectiveToken, isGuest, isLoading, login, register, verifyEmail, resendVerification, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
```

- [ ] **Step 2: Commit**

```bash
git add epub-tts-frontend/src/contexts/AuthContext.tsx
git commit -m "feat(auth): dual token storage with refresh logic in AuthContext"
```

---

### Task 7: Update Frontend — API Services Token Key

**Files:**
- Modify: `epub-tts-frontend/src/api/services.ts`

- [ ] **Step 1: Update getEffectiveToken to use new localStorage keys**

Change the `getEffectiveToken` function at the top of `services.ts`:

```typescript
// Old:
function getEffectiveToken(): string | null {
  return localStorage.getItem("auth_token") || localStorage.getItem("guest_token");
}

// New:
function getEffectiveToken(): string | null {
  return localStorage.getItem("auth_access_token") || localStorage.getItem("guest_access_token");
}
```

- [ ] **Step 2: Commit**

```bash
git add epub-tts-frontend/src/api/services.ts
git commit -m "feat(auth): update token storage keys in API services"
```

---

### Task 8: Smoke Test — Manual Verification

**Files:** None (testing only)

- [ ] **Step 1: Start backend and verify it loads without import errors**

Run: `cd /Users/caiqj/project/private/BookReader/epub-tts-backend && timeout 10 python -c "from app.routers.auth import router; from app.services.session_service import create_session; from app.middleware.auth import get_current_session; print('All imports OK')" 2>&1 || true`
Expected: `All imports OK`

- [ ] **Step 2: Verify frontend compiles**

Run: `cd /Users/caiqj/project/private/BookReader/epub-tts-frontend && npx tsc --noEmit 2>&1 | head -20`
Expected: No errors (or only pre-existing ones)

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix(auth): address import/compile issues from multi-device auth"
```
