"""
Reading routes: progress and stats, merged from reading_progress.py and reading_stats.py.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from shared.models import Book
from shared.database import get_db
from app.services.reading_progress_service import ReadingProgressService
from app.services.reading_stats_service import ReadingStatsService
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/reading", tags=["reading"])


class SaveProgressRequest(BaseModel):
    chapter_href: str
    paragraph_index: int = Field(ge=0)
    chapter_index: int | None = Field(default=None, ge=0)
    total_chapters: int | None = Field(default=None, ge=1)


class HeartbeatRequest(BaseModel):
    book_id: str
    seconds: int = Field(default=30, ge=1)


# --- Progress ---

@router.get("/progress/{book_id}")
async def get_progress(
    book_id: str,
    user_id: str = Depends(get_current_user),
):
    return ReadingProgressService.get(user_id, book_id)


@router.put("/progress/{book_id}")
async def save_progress(
    book_id: str,
    req: SaveProgressRequest,
    user_id: str = Depends(get_current_user),
):
    ReadingProgressService.save(
        user_id,
        book_id,
        req.chapter_href,
        req.paragraph_index,
        req.chapter_index,
        req.total_chapters,
    )
    return {"ok": True}


# --- Stats ---

@router.post("/stats/heartbeat")
async def heartbeat(
    req: HeartbeatRequest,
    user_id: str = Depends(get_current_user),
):
    with get_db() as db:
        book = db.query(Book).filter(Book.id == req.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if not book.is_public and book.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    ReadingStatsService.heartbeat(user_id, req.book_id, req.seconds)
    return {"ok": True}


@router.get("/stats/heatmap")
async def get_heatmap(
    year: int,
    user_id: str = Depends(get_current_user),
):
    return ReadingStatsService.get_heatmap(user_id, year)


@router.get("/stats/books")
async def get_book_stats(
    user_id: str = Depends(get_current_user),
):
    return ReadingStatsService.get_book_stats(user_id)


@router.get("/stats/summary")
async def get_summary(
    user_id: str = Depends(get_current_user),
):
    return ReadingStatsService.get_summary(user_id)
