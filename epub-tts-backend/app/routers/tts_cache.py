"""
TTS cache management routes: stats, chapter cache, clear cache.
"""
from fastapi import APIRouter, HTTPException, Depends

from app.services.tts.cache import AudioCache
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/tts/cache", tags=["tts-cache"])


@router.get("/stats")
async def get_cache_stats(book_id: str, user_id: str = Depends(get_current_user)):
    return AudioCache.get_cache_stats(user_id, book_id)


@router.get("/chapter")
async def get_chapter_cache(book_id: str, chapter_href: str, user_id: str = Depends(get_current_user)):
    entries = AudioCache.get_chapter_cached_entries(book_id, chapter_href, user_id)
    return {
        "book_id": book_id,
        "chapter_href": chapter_href,
        "entries": entries,
        "cached_count": len(entries)
    }


@router.delete("")
async def clear_cache(book_id: str, user_id: str = Depends(get_current_user)):
    count = AudioCache.clear_cache(user_id, book_id)
    return {"message": f"已清除 {count} 个缓存文件", "cleared_count": count}
