"""
Voice routes: list voices, clone, manage cloned voices, voice preferences.
"""
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import Optional
from loguru import logger

from shared.schemas.tts_config import VoicePreferenceIn, VoicePreferenceOut
from shared.models import UserPreferences, ClonedVoice
from shared.database import get_db
from shared.config import settings
from app.deps import is_minimax_configured, get_minimax_credentials
from app.services.voice_clone import VoiceCloneService
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/voices", tags=["voices"])


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


@router.get("")
async def get_voices(user_id: str = Depends(get_current_user)):
    """Get voices based on user's configured TTS provider"""
    minimax_configured = is_minimax_configured(user_id)
    voices = []

    # Always include Edge TTS voices
    from app.services.tts.facade import TTSFacade as TTSService
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


@router.get("/edge")
async def get_edge_voices():
    """Get Edge TTS voices"""
    from app.services.tts.facade import TTSFacade as TTSService
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


@router.get("/minimax")
async def get_minimax_voices(
    lang: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    """Get MiniMax TTS system voices, optionally filtered by language prefix (e.g. 'zh', 'en')"""
    if not is_minimax_configured(user_id):
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


@router.post("/clone")
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

    api_key, base_url = get_minimax_credentials(user_id)

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


@router.get("/cloned")
async def get_cloned_voices(user_id: str = Depends(get_current_user)):
    """Get user's cloned voices"""
    minimax_configured = is_minimax_configured(user_id)

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


@router.delete("/cloned/{voice_id}")
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

        db.delete(voice)
        db.commit()

    return {"message": "Voice deleted successfully"}


@router.get("/preferences", response_model=VoicePreferenceOut)
async def get_voice_preferences(user_id: str = Depends(get_current_user)):
    """Get user's voice preferences"""
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()

        if not prefs:
            # Hardcoded defaults — admin SystemSetting does NOT affect regular users
            return VoicePreferenceOut(
                active_voice_type="edge",
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


@router.put("/preferences")
async def save_voice_preferences(
    prefs_in: VoicePreferenceIn,
    user_id: str = Depends(get_current_user)
):
    """Save user's voice preferences"""

    with get_db() as db:
        existing = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
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
            prefs = UserPreferences(
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
