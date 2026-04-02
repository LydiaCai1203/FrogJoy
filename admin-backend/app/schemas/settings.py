from pydantic import BaseModel
from typing import Optional


class SystemSettings(BaseModel):
    guest_rate_limit_tts: int = 5
    guest_rate_limit_translation: int = 1
    guest_rate_limit_chat: int = 1
    default_tts_provider: str = "edge-tts"
    default_theme: str = "eye-care"
    default_font_size: int = 18
    allow_registration: bool = True


class SystemSettingsUpdate(BaseModel):
    guest_rate_limit_tts: Optional[int] = None
    guest_rate_limit_translation: Optional[int] = None
    guest_rate_limit_chat: Optional[int] = None
    default_tts_provider: Optional[str] = None
    default_theme: Optional[str] = None
    default_font_size: Optional[int] = None
    allow_registration: Optional[bool] = None
