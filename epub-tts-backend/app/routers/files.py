import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from shared.config import settings
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/files", tags=["files"])

AVATAR_MEDIA_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

DEFAULT_AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "default_avatars")


@router.get("/default-avatar/{filename}")
async def serve_default_avatar(filename: str):
    """Serve default frog avatar image. No auth required."""
    safe_name = os.path.basename(filename)
    filepath = os.path.join(DEFAULT_AVATAR_DIR, safe_name)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Default avatar not found")
    ext = safe_name.rsplit(".", 1)[-1].lower()
    media_type = AVATAR_MEDIA_TYPES.get(ext, "image/png")
    return FileResponse(filepath, media_type=media_type)


@router.get("/avatar/{user_id}")
async def serve_avatar(user_id: str):
    """Serve user avatar image. No auth required."""
    avatar_dir = os.path.join(settings.data_dir, "users", user_id)
    if os.path.isdir(avatar_dir):
        for fname in os.listdir(avatar_dir):
            if fname.startswith("avatar."):
                ext = fname.rsplit(".", 1)[-1].lower()
                media_type = AVATAR_MEDIA_TYPES.get(ext, "image/jpeg")
                return FileResponse(os.path.join(avatar_dir, fname), media_type=media_type)
    raise HTTPException(status_code=404, detail="Avatar not found")


@router.get("/audio/{user_id}/{book_id}/{filename}")
async def serve_audio(user_id: str, book_id: str, filename: str):
    """Serve audio file. No auth — browser <audio> tag can't send Bearer token."""
    filepath = os.path.join(settings.get_audio_dir(user_id, book_id), filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(filepath, media_type="audio/mpeg")


@router.get("/{user_id}/{book_id}/audio/{filename}")
async def serve_audio_legacy(user_id: str, book_id: str, filename: str):
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
