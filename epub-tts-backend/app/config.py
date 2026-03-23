from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ElevenLabs API Configuration
    elevenlabs_api_key: str = ""
    
    # Audio Configuration
    audio_dir: str = "data/audio"
    uploads_dir: str = "data/uploads"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# 便捷访问
settings = get_settings()

