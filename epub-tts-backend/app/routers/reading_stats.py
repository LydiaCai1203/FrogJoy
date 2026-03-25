from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.middleware.auth import get_current_user
from app.services.reading_stats_service import ReadingStatsService

router = APIRouter(prefix="/reading-stats", tags=["reading-stats"])


class HeartbeatRequest(BaseModel):
    book_id: str
    seconds: int = Field(default=30, ge=1)


@router.post("/heartbeat")
async def heartbeat(
    req: HeartbeatRequest,
    user_id: str = Depends(get_current_user),
):
    ReadingStatsService.heartbeat(user_id, req.book_id, req.seconds)
    return {"ok": True}


@router.get("/heatmap")
async def get_heatmap(
    year: int,
    user_id: str = Depends(get_current_user),
):
    return ReadingStatsService.get_heatmap(user_id, year)


@router.get("/books")
async def get_book_stats(
    user_id: str = Depends(get_current_user),
):
    return ReadingStatsService.get_book_stats(user_id)


@router.get("/summary")
async def get_summary(
    user_id: str = Depends(get_current_user),
):
    return ReadingStatsService.get_summary(user_id)
