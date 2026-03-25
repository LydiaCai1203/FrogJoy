from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.middleware.auth import get_current_user
from app.services.reading_progress_service import ReadingProgressService

router = APIRouter(prefix="/reading-progress", tags=["reading-progress"])


class SaveProgressRequest(BaseModel):
    chapter_href: str
    paragraph_index: int


@router.get("/{book_id}")
async def get_progress(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    return ReadingProgressService.get(user_id, book_id)


@router.put("/{book_id}")
async def save_progress(
    book_id: str,
    req: SaveProgressRequest,
    user_id: str = Depends(get_current_user),
):
    ReadingProgressService.save(user_id, book_id, req.chapter_href, req.paragraph_index)
    return {"ok": True}
