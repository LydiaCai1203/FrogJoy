from pydantic import BaseModel
from typing import Optional


class TTSConfigIn(BaseModel):
    api_key: str
    base_url: Optional[str] = None  # Optional override, defaults to settings.minimax_base_url


class TTSConfigOut(BaseModel):
    has_api_key: bool = False
    base_url: str = ""


class VoicePreferenceIn(BaseModel):
    active_voice_type: Optional[str] = None  # "edge" | "minimax" | "cloned"
    active_edge_voice: Optional[str] = None
    active_minimax_voice: Optional[str] = None
    active_cloned_voice_id: Optional[str] = None
    speed: Optional[int] = None
    pitch: Optional[int] = None
    emotion: Optional[str] = None
    audio_persistent: Optional[bool] = None


class VoicePreferenceOut(BaseModel):
    active_voice_type: str
    active_edge_voice: str
    active_minimax_voice: Optional[str] = None
    active_cloned_voice_id: Optional[str] = None
    speed: int
    pitch: int
    emotion: str
    audio_persistent: bool


class ProviderStatus(BaseModel):
    edge_tts_configured: bool
    minimax_tts_configured: bool
