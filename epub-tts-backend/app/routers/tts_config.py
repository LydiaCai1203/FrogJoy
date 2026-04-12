import os
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from app.middleware.auth import get_current_user
from app.models.database import get_db
from app.models.models import TTSProviderConfig, ClonedVoice, VoicePreferences, UserFeatureSetup
from app.services.auth_service import AuthService
from app.services.voice_clone import VoiceCloneService
from app.config import settings
from app.middleware.rate_limit import is_guest_user

router = APIRouter()


# --- Data Models ---
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


# --- TTS Provider Config Routes ---
@router.get("/tts/config", response_model=TTSConfigOut)
async def get_tts_config(user_id: str = Depends(get_current_user)):
    """Get current TTS provider configuration"""

    with get_db() as db:
        config = db.query(TTSProviderConfig).filter(
            TTSProviderConfig.user_id == user_id
        ).first()

        if not config:
            return TTSConfigOut(has_api_key=False, base_url=settings.minimax_base_url)

        return TTSConfigOut(
            has_api_key=bool(config.api_key_encrypted),
            base_url=config.base_url or settings.minimax_base_url,
        )


@router.put("/tts/config")
async def save_tts_config(
    config_in: TTSConfigIn,
    user_id: str = Depends(get_current_user)
):
    """Save MiniMax TTS configuration (validates API key first)"""

    if not config_in.api_key:
        raise HTTPException(status_code=400, detail="API key is required")

    # Validate API key
    effective_base_url = config_in.base_url or settings.minimax_base_url
    is_valid = await VoiceCloneService.validate_api_key(
        config_in.api_key, base_url=effective_base_url
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail="API key is invalid or unauthorized")

    encrypted_key = AuthService.encrypt_api_key(config_in.api_key)

    with get_db() as db:
        existing = db.query(TTSProviderConfig).filter(
            TTSProviderConfig.user_id == user_id
        ).first()

        if existing:
            existing.provider_type = "minimax-tts"
            existing.base_url = config_in.base_url  # None means use default
            existing.api_key_encrypted = encrypted_key
        else:
            config = TTSProviderConfig(
                user_id=user_id,
                provider_type="minimax-tts",
                base_url=config_in.base_url,
                api_key_encrypted=encrypted_key,
            )
            db.add(config)

        # Mark voice_synthesis_configured as true
        feature_setup = db.query(UserFeatureSetup).filter(
            UserFeatureSetup.user_id == user_id
        ).first()
        if feature_setup:
            feature_setup.voice_synthesis_configured = True
        else:
            feature_setup = UserFeatureSetup(
                user_id=user_id,
                voice_synthesis_configured=True,
            )
            db.add(feature_setup)

        db.commit()

    return {"message": "MiniMax TTS configured successfully"}


@router.delete("/tts/config")
async def delete_tts_config(user_id: str = Depends(get_current_user)):
    """Remove MiniMax TTS configuration and reset voice preferences to Edge"""

    with get_db() as db:
        config = db.query(TTSProviderConfig).filter(
            TTSProviderConfig.user_id == user_id
        ).first()

        if config:
            config.api_key_encrypted = None
            config.base_url = None
            config.provider_type = "edge-tts"

        # Reset voice preferences to edge if currently using minimax/cloned
        prefs = db.query(VoicePreferences).filter(
            VoicePreferences.user_id == user_id
        ).first()
        if prefs and prefs.active_voice_type in ("minimax", "cloned"):
            prefs.active_voice_type = "edge"
            prefs.active_edge_voice = prefs.active_edge_voice or "zh-CN-XiaoxiaoNeural"

        db.commit()

    return {"message": "MiniMax TTS configuration removed"}


# --- Voice List Routes ---
@router.get("/tts/voices")
async def get_voices(user_id: str = Depends(get_current_user)):
    """Get voices based on user's configured TTS provider"""
    minimax_configured = _is_minimax_configured(user_id)
    voices = []

    # Always include Edge TTS voices
    from app.services.tts_service import TTSService
    edge_voices = await TTSService.get_voices()
    chinese_edge = [v for v in edge_voices if v["lang"].startswith("zh")]

    for v in chinese_edge:
        voices.append({
            "type": "edge",
            "name": v["name"],
            "displayName": _EDGE_DISPLAY_NAMES.get(v["name"], v["name"]),
            "gender": v["gender"],
            "lang": v["lang"]
        })

    # Add MiniMax Chinese voices if configured
    if minimax_configured:
        minimax_voices = VoiceCloneService.get_minimax_voices_sync()
        for v in minimax_voices:
            if v.get("lang", "").startswith("zh"):
                voices.append({
                    "type": "minimax",
                    "name": v["voice_id"],
                    "displayName": v.get("name", v["voice_id"]),
                    "gender": v.get("gender", "Unknown"),
                    "lang": v.get("lang", "zh"),
                })

    # Add user's cloned voices
    with get_db() as db:
        cloned = db.query(ClonedVoice).filter(
            ClonedVoice.user_id == user_id
        ).order_by(ClonedVoice.created_at.desc()).all()
        for v in cloned:
            voices.append({
                "type": "cloned",
                "id": v.id,
                "name": v.voice_id,
                "displayName": v.name,
                "gender": "Unknown",
                "lang": v.lang or "zh",
            })

    return voices


@router.get("/tts/voices/edge")
async def get_edge_voices():
    """Get Edge TTS voices"""
    from app.services.tts_service import TTSService
    voices = await TTSService.get_voices()
    chinese_voices = [v for v in voices if v["lang"].startswith("zh")]

    return [
        {
            "name": v["name"],
            "displayName": _EDGE_DISPLAY_NAMES.get(v["name"], v["name"]),
            "gender": v["gender"],
            "lang": v["lang"],
        }
        for v in chinese_voices
    ]


@router.get("/tts/voices/minimax")
async def get_minimax_voices(
    lang: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    """Get MiniMax TTS system voices, optionally filtered by language prefix (e.g. 'zh', 'en')"""
    if not _is_minimax_configured(user_id):
        raise HTTPException(status_code=400, detail="MiniMax TTS not configured")
    raw = VoiceCloneService.get_minimax_voices_sync()
    return [
        {
            "type": "minimax",
            "name": v["voice_id"],
            "displayName": v.get("name", v["voice_id"]),
            "gender": v.get("gender", "Unknown"),
            "lang": v.get("lang", "zh"),
        }
        for v in raw
        if not lang or v.get("lang", "").startswith(lang)
    ]


# --- Voice Clone Routes ---
@router.post("/tts/voices/clone")
async def clone_voice(
    name: str = Form(...),
    lang: str = Form("zh"),
    audio_file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """Upload audio sample and clone voice using MiniMax API"""

    # Validate file type
    allowed_types = ["audio/wav", "audio/mpeg", "audio/mp3", "audio/x-wav", "audio/wave", "audio/x-m4a", "audio/mp4"]
    if audio_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {audio_file.content_type}. Supported: WAV, MP3, M4A"
        )

    # Read file content
    content = await audio_file.read()
    file_size = len(content)

    if file_size > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    if file_size < 1000:
        raise HTTPException(status_code=400, detail="File too small or empty")

    api_key, base_url = _get_minimax_credentials(user_id)

    # Save audio sample to disk
    voice_uuid = str(uuid.uuid4())
    sample_dir = os.path.join(settings.data_dir, "users", user_id, "voice_samples")
    os.makedirs(sample_dir, exist_ok=True)

    ext = os.path.splitext(audio_file.filename)[1] or ".wav"
    sample_path = os.path.join(sample_dir, f"{voice_uuid}{ext}")

    with open(sample_path, "wb") as f:
        f.write(content)

    # Call MiniMax API to clone voice
    try:
        result = await VoiceCloneService.clone_voice(
            api_key=api_key,
            audio_sample_path=sample_path,
            name=name,
            user_id=user_id,
            lang=lang,
            base_url=base_url,
        )

        # Save cloned voice to database
        with get_db() as db:
            cloned = ClonedVoice(
                id=str(uuid.uuid4()),
                user_id=user_id,
                voice_id=result["voice_id"],
                name=name,
                audio_sample_path=sample_path,
                lang=lang,
            )
            db.add(cloned)

            # Mark voice_selection_configured as true
            feature_setup = db.query(UserFeatureSetup).filter(
                UserFeatureSetup.user_id == user_id
            ).first()
            if feature_setup:
                feature_setup.voice_selection_configured = True
            else:
                feature_setup = UserFeatureSetup(
                    user_id=user_id,
                    voice_selection_configured=True,
                )
                db.add(feature_setup)

            db.commit()

        return {
            "message": "Voice cloned successfully",
            "voice_id": result["voice_id"],
            "name": name,
            "lang": lang,
        }

    except Exception as e:
        # Clean up sample file on failure
        if os.path.exists(sample_path):
            os.remove(sample_path)
        logger.error(f"Voice clone failed: {e}")
        raise HTTPException(status_code=500, detail=f"Voice clone failed: {str(e)}")


@router.get("/tts/voices/cloned")
async def get_cloned_voices(user_id: str = Depends(get_current_user)):
    """Get user's cloned voices"""
    minimax_configured = _is_minimax_configured(user_id)

    with get_db() as db:
        voices = db.query(ClonedVoice).filter(
            ClonedVoice.user_id == user_id
        ).order_by(ClonedVoice.created_at.desc()).all()

        return [
            {
                "id": v.id,
                "voice_id": v.voice_id,
                "name": v.name,
                "lang": v.lang,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "available": minimax_configured,
            }
            for v in voices
        ]


@router.delete("/tts/voices/cloned/{voice_id}")
async def delete_cloned_voice(
    voice_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a cloned voice"""

    with get_db() as db:
        voice = db.query(ClonedVoice).filter(
            ClonedVoice.id == voice_id,
            ClonedVoice.user_id == user_id
        ).first()

        if not voice:
            raise HTTPException(status_code=404, detail="Voice not found")

        # Delete sample file
        if voice.audio_sample_path and os.path.exists(voice.audio_sample_path):
            try:
                os.remove(voice.audio_sample_path)
            except Exception:
                pass

        # Reset voice preferences if this was the active cloned voice
        prefs = db.query(VoicePreferences).filter(
            VoicePreferences.user_id == user_id
        ).first()
        if prefs and prefs.active_voice_type == "cloned" and prefs.active_cloned_voice_id == voice_id:
            prefs.active_voice_type = "edge"
            prefs.active_edge_voice = prefs.active_edge_voice or "zh-CN-XiaoxiaoNeural"
            prefs.active_cloned_voice_id = None

        db.delete(voice)
        db.commit()

    return {"message": "Voice deleted successfully"}


# --- Voice Preferences Routes ---
@router.get("/tts/voice-preferences", response_model=VoicePreferenceOut)
async def get_voice_preferences(user_id: str = Depends(get_current_user)):
    """Get user's voice preferences"""
    with get_db() as db:
        prefs = db.query(VoicePreferences).filter(
            VoicePreferences.user_id == user_id
        ).first()

        if not prefs:
            from app.services.system_settings import get_system_setting
            default_provider = get_system_setting("default_tts_provider", "edge-tts")
            # Map provider name to voice_type: "edge-tts" -> "edge", "minimax-tts" -> "minimax"
            default_voice_type = default_provider.replace("-tts", "") if default_provider else "edge"
            return VoicePreferenceOut(
                active_voice_type=default_voice_type,
                active_edge_voice="zh-CN-XiaoxiaoNeural",
                speed=100,
                pitch=0,
                emotion="neutral",
                audio_persistent=False,
            )

        return VoicePreferenceOut(
            active_voice_type=prefs.active_voice_type,
            active_edge_voice=prefs.active_edge_voice or "zh-CN-XiaoxiaoNeural",
            active_minimax_voice=prefs.active_minimax_voice,
            active_cloned_voice_id=prefs.active_cloned_voice_id,
            speed=prefs.speed or 100,
            pitch=prefs.pitch or 0,
            emotion=prefs.emotion or "neutral",
            audio_persistent=prefs.audio_persistent or False,
        )


@router.put("/tts/voice-preferences")
async def save_voice_preferences(
    prefs_in: VoicePreferenceIn,
    user_id: str = Depends(get_current_user)
):
    """Save user's voice preferences"""

    with get_db() as db:
        existing = db.query(VoicePreferences).filter(
            VoicePreferences.user_id == user_id
        ).first()

        if existing:
            if prefs_in.active_voice_type is not None:
                existing.active_voice_type = prefs_in.active_voice_type
            if prefs_in.active_edge_voice is not None:
                existing.active_edge_voice = prefs_in.active_edge_voice
            if prefs_in.active_minimax_voice is not None:
                existing.active_minimax_voice = prefs_in.active_minimax_voice
            if prefs_in.active_cloned_voice_id is not None:
                existing.active_cloned_voice_id = prefs_in.active_cloned_voice_id
            if prefs_in.speed is not None:
                existing.speed = prefs_in.speed
            if prefs_in.pitch is not None:
                existing.pitch = prefs_in.pitch
            if prefs_in.emotion is not None:
                existing.emotion = prefs_in.emotion
            if prefs_in.audio_persistent is not None:
                existing.audio_persistent = prefs_in.audio_persistent
        else:
            prefs = VoicePreferences(
                user_id=user_id,
                active_voice_type=prefs_in.active_voice_type or "edge",
                active_edge_voice=prefs_in.active_edge_voice or "zh-CN-XiaoxiaoNeural",
                active_minimax_voice=prefs_in.active_minimax_voice,
                active_cloned_voice_id=prefs_in.active_cloned_voice_id,
                speed=prefs_in.speed or 100,
                pitch=prefs_in.pitch or 0,
                emotion=prefs_in.emotion or "neutral",
                audio_persistent=prefs_in.audio_persistent or False,
            )
            db.add(prefs)

        db.commit()

    return {"message": "Voice preferences saved successfully"}


# --- Provider Status Route ---
@router.get("/tts/providers/status", response_model=ProviderStatus)
async def get_provider_status(user_id: str = Depends(get_current_user)):
    """Check which TTS providers are configured"""
    return ProviderStatus(
        edge_tts_configured=True,
        minimax_tts_configured=_is_minimax_configured(user_id),
    )


# --- Helpers ---

_EDGE_DISPLAY_NAMES = {
    "zh-CN-XiaoxiaoNeural": "晓晓（活泼女声）",
    "zh-CN-XiaoyiNeural": "晓伊（温柔女声）",
    "zh-CN-YunjianNeural": "云健（成熟男声）",
    "zh-CN-YunxiNeural": "云希（年轻男声）",
    "zh-CN-YunxiaNeural": "云夏（少年音）",
    "zh-CN-YunyangNeural": "云扬（新闻播报）",
    "zh-CN-liaoning-XiaobeiNeural": "晓北（东北话）",
    "zh-CN-shaanxi-XiaoniNeural": "晓妮（陕西话）",
    "zh-HK-HiuGaaiNeural": "曉佳（粤语女声）",
    "zh-HK-HiuMaanNeural": "曉曼（粤语女声）",
    "zh-HK-WanLungNeural": "雲龍（粤语男声）",
    "zh-TW-HsiaoChenNeural": "曉臻（台湾女声）",
    "zh-TW-HsiaoYuNeural": "曉雨（台湾女声）",
    "zh-TW-YunJheNeural": "雲哲（台湾男声）",
}


def _is_minimax_configured(user_id: str) -> bool:
    """Check if user has a valid MiniMax API key configured."""
    with get_db() as db:
        config = db.query(TTSProviderConfig).filter(
            TTSProviderConfig.user_id == user_id
        ).first()
        return config is not None and bool(config.api_key_encrypted)


def _get_minimax_credentials(user_id: str) -> tuple[str, Optional[str]]:
    """Get MiniMax API key and optional base_url override for user. Raises 400 if not configured."""
    with get_db() as db:
        config = db.query(TTSProviderConfig).filter(
            TTSProviderConfig.user_id == user_id
        ).first()

    if not config or not config.api_key_encrypted:
        raise HTTPException(status_code=400, detail="MiniMax TTS not configured")

    api_key = AuthService.decrypt_api_key(config.api_key_encrypted)
    return api_key, config.base_url
