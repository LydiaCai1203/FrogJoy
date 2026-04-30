from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import uuid
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_fernet() -> Fernet:
    """Get or create a Fernet cipher using Fernet key from settings."""
    from shared.config import settings
    key = settings.fernet_key
    if not key:
        key = Fernet.generate_key().decode()
        import warnings
        warnings.warn("FERNET_KEY not set, using a random key (will not persist across restarts)")
    if isinstance(key, str):
        key = key.encode()
    if len(key) == 32:
        key = base64.urlsafe_b64encode(key)
    return Fernet(key)


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

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

    @staticmethod
    def generate_user_id() -> str:
        return str(uuid.uuid4())

    # ----- API Key Encryption -----

    @staticmethod
    def encrypt_api_key(api_key: str) -> str:
        """Encrypt an API key using Fernet symmetric encryption."""
        fernet = _get_fernet()
        return fernet.encrypt(api_key.encode()).decode()

    @staticmethod
    def decrypt_api_key(encrypted_key: str) -> str:
        """Decrypt an API key."""
        fernet = _get_fernet()
        return fernet.decrypt(encrypted_key.encode()).decode()
