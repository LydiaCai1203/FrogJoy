import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ElevenLabs API Configuration
    elevenlabs_api_key: str = ""

    # MiniMax TTS Configuration
    minimax_base_url: str = "https://api.minimaxi.com"

    # MiniMax LLM (概念提取)
    minimax_llm_api_key: str = ""
    minimax_llm_base_url: str = "https://api.minimaxi.com/anthropic"
    minimax_llm_model: str = "MiniMax-M2.7"

    # Embedding (概念去重 + 语义匹配)
    embedding_api_key: str = ""
    embedding_base_url: str = "https://model-square.app.baizhi.cloud/v1/embeddings"
    embedding_model: str = "bge-m3"

    # AI API Key Encryption
    fernet_key: str = ""

    # Data directory root
    data_dir: str = "data"

    # SMTP Configuration
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    app_url: str = "https://deepkb.com.cn"

    # Agent Server (A2A)
    agent_server_url: str = "http://agent-server:9000"

    # Guest account
    guest_email: str = ""

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

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

    def get_translation_dir(self, user_id: str, book_id: str, target_lang: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "translations", target_lang)

    def get_translation_path(self, user_id: str, book_id: str, target_lang: str, chapter_href: str) -> str:
        import hashlib
        chapter_hash = hashlib.md5(chapter_href.encode("utf-8")).hexdigest()
        return os.path.join(self.get_translation_dir(user_id, book_id, target_lang), f"{chapter_hash}.json")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
