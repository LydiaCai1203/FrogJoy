import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/bookreader",
    )
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_days: int = 7

    host: str = "0.0.0.0"
    port: int = 8001

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
