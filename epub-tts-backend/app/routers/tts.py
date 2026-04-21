"""
TTS routes: speak, prefetch, serve temporary audio.
"""
import os
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from loguru import logger

from shared.schemas.tts import TTSRequest, PrefetchRequest
from app.deps import is_audio_persistent
from app.services.tts.facade import TTSFacade as TTSService
from app.services.tts.memory import memory_cache, _tmp_audio_dir
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("/speak")
async def speak(request: TTSRequest, raw_request: Request, user_id: str = Depends(get_current_user)):
    logger.debug(f"[API] TTS request: text='{request.text[:100] if request.text else 'EMPTY'}...', voice={request.voice}, voice_type={request.voice_type}")

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    persistent = is_audio_persistent(user_id)

    try:
        result = await TTSService.generate_audio(
            text=request.text,
            voice=request.voice,
            voice_type=request.voice_type,
            rate=request.rate,
            pitch=request.pitch,
            user_id=user_id,
            book_id=request.book_id,
            chapter_href=request.chapter_href,
            paragraph_index=request.paragraph_index,
            is_translated=request.is_translated or False,
            persistent=persistent,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prefetch")
async def prefetch_audio(request: PrefetchRequest, user_id: str = Depends(get_current_user)):
    try:
        persistent = is_audio_persistent(user_id)

        await memory_cache.prefetch_range(
            book_id=request.book_id,
            chapter_href=request.chapter_href,
            start_index=request.start_index,
            end_index=request.end_index,
            sentences=request.sentences,
            voice=request.voice,
            voice_type=request.voice_type or "edge",
            rate=request.rate,
            pitch=request.pitch,
            user_id=user_id,
            persistent=persistent,
        )

        return {
            "success": True,
            "prefetched": request.end_index - request.start_index,
            "cache_stats": memory_cache.get_stats()
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tmp/{filename}")
async def serve_tmp_audio(filename: str):
    """Serve temporary (non-persistent) audio files."""
    filepath = os.path.join(_tmp_audio_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Temporary audio file not found")
    return FileResponse(filepath, media_type="audio/mpeg")
