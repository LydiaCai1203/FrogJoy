from shared.config import Settings as _SharedSettings, get_settings as _get_shared_settings
from functools import lru_cache
import os


class Settings(_SharedSettings):
    """Admin-backend settings: extends shared settings with JWT config."""
    secret_key: str = os.environ.get("SECRET_KEY", "your-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_days: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
