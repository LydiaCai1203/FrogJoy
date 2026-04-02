from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, cast, Date
from app.database import get_db
from app.models import User, Book, ReadingStat
from app.dependencies import get_admin_user
from app.schemas.dashboard import (
    OverviewStats,
    UserGrowthResponse, GrowthPoint,
    ReadingStatsResponse, ReadingStatsPoint,
    ActiveUsersResponse, ActiveUserItem,
)

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


@router.get("/overview", response_model=OverviewStats)
async def get_overview(_admin: str = Depends(get_admin_user)):
    today = date.today().isoformat()
    with get_db() as db:
        total_users = db.query(func.count(User.id)).scalar()
        verified_users = db.query(func.count(User.id)).filter(User.is_verified == True).scalar()
        admin_users = db.query(func.count(User.id)).filter(User.is_admin == True).scalar()
        total_books = db.query(func.count(Book.id)).scalar()
        total_reading = (
            db.query(func.coalesce(func.sum(ReadingStat.duration_seconds), 0)).scalar()
        )
        today_active = (
            db.query(func.count(func.distinct(ReadingStat.user_id)))
            .filter(ReadingStat.date == today)
            .scalar()
        )

        return OverviewStats(
            total_users=total_users,
            total_books=total_books,
            total_reading_seconds=total_reading,
            today_active_users=today_active,
            verified_users=verified_users,
            admin_users=admin_users,
        )


@router.get("/user-growth", response_model=UserGrowthResponse)
async def get_user_growth(
    days: int = Query(30, ge=1, le=365),
    _admin: str = Depends(get_admin_user),
):
    since = date.today() - timedelta(days=days)
    with get_db() as db:
        rows = (
            db.query(
                cast(User.created_at, Date).label("d"),
                func.count(User.id),
            )
            .filter(cast(User.created_at, Date) >= since)
            .group_by("d")
            .order_by("d")
            .all()
        )

        data = [GrowthPoint(date=str(r[0]), count=r[1]) for r in rows]
        return UserGrowthResponse(data=data)


@router.get("/reading-stats", response_model=ReadingStatsResponse)
async def get_reading_stats(
    days: int = Query(30, ge=1, le=365),
    _admin: str = Depends(get_admin_user),
):
    since = (date.today() - timedelta(days=days)).isoformat()
    with get_db() as db:
        rows = (
            db.query(
                ReadingStat.date,
                func.sum(ReadingStat.duration_seconds),
                func.count(func.distinct(ReadingStat.user_id)),
            )
            .filter(ReadingStat.date >= since)
            .group_by(ReadingStat.date)
            .order_by(ReadingStat.date)
            .all()
        )

        data = [
            ReadingStatsPoint(date=r[0], total_seconds=r[1], active_users=r[2])
            for r in rows
        ]
        return ReadingStatsResponse(data=data)


@router.get("/active-users", response_model=ActiveUsersResponse)
async def get_active_users(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    _admin: str = Depends(get_admin_user),
):
    since = (date.today() - timedelta(days=days)).isoformat()
    with get_db() as db:
        rows = (
            db.query(
                ReadingStat.user_id,
                User.email,
                func.sum(ReadingStat.duration_seconds).label("total"),
                func.count(func.distinct(ReadingStat.date)).label("days"),
                User.last_login_at,
            )
            .join(User, User.id == ReadingStat.user_id)
            .filter(ReadingStat.date >= since)
            .group_by(ReadingStat.user_id, User.email, User.last_login_at)
            .order_by(func.sum(ReadingStat.duration_seconds).desc())
            .limit(limit)
            .all()
        )

        data = [
            ActiveUserItem(
                user_id=r.user_id,
                email=r.email,
                total_reading_seconds=r.total,
                reading_days=r.days,
                last_login_at=r.last_login_at.isoformat() if r.last_login_at else None,
            )
            for r in rows
        ]
        return ActiveUsersResponse(data=data)
