"""
TTS provider configuration routes: get/save/delete config, provider status.
"""
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from shared.schemas.tts_config import TTSConfigIn, TTSConfigOut, ProviderStatus
from shared.models import TTSProviderConfig, UserPreferences
from shared.database import get_db
from shared.config import settings
from app.deps import is_minimax_configured
from app.services.auth_service import AuthService
from app.services.voice_clone import VoiceCloneService
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/tts", tags=["tts-config"])


@router.get("/config", response_model=TTSConfigOut)
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


@router.put("/config")
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

        db.commit()

    return {"message": "MiniMax TTS configured successfully"}


@router.delete("/config")
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
        prefs = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()
        if prefs and prefs.active_voice_type in ("minimax", "cloned"):
            prefs.active_voice_type = "edge"
            prefs.active_edge_voice = prefs.active_edge_voice or "zh-CN-XiaoxiaoNeural"

        db.commit()

    return {"message": "MiniMax TTS configuration removed"}


@router.get("/providers/status", response_model=ProviderStatus)
async def get_provider_status(user_id: str = Depends(get_current_user)):
    """Check which TTS providers are configured"""
    return ProviderStatus(
        edge_tts_configured=True,
        minimax_tts_configured=is_minimax_configured(user_id),
    )
