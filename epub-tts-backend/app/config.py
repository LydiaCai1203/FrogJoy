import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ElevenLabs API Configuration
    elevenlabs_api_key: str = ""

    # AI API Key Encryption
    fernet_key: str = ""

    # Data directory root
    data_dir: str = "data"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    # --- Path helpers ---

    def get_user_book_dir(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.data_dir, "users", user_id, book_id)

    def get_book_path(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "book.epub")

    def get_cover_path(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "cover.jpg")

    def get_audio_dir(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "audio")

    def get_cache_index_path(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "cache_index.json")

    def get_images_dir(self, book_id: str) -> str:
        return os.path.join(self.data_dir, "images", book_id)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
