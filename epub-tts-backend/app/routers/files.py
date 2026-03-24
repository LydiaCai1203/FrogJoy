import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.config import settings

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{user_id}/{book_id}/audio/{filename}")
async def serve_audio(user_id: str, book_id: str, filename: str):
    filepath = os.path.join(settings.get_audio_dir(user_id, book_id), filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(filepath, media_type="audio/mpeg")


@router.get("/{user_id}/{book_id}/cover.jpg")
async def serve_cover(user_id: str, book_id: str):
    filepath = settings.get_cover_path(user_id, book_id)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Cover not found")
    return FileResponse(filepath, media_type="image/jpeg")
