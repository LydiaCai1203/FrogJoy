from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, case
from app.database import get_db
from app.models import User, Book, ReadingStat, Highlight
from app.dependencies import get_admin_user
from app.redis_client import get_redis
from app.schemas.user import (
    UserListResponse, UserListItem, UserDetail, UserUpdate, UserStats,
)

ACTIVE_KEY_PREFIX = "user:last_active:"

router = APIRouter(prefix="/users", tags=["admin-users"])


@router.get("/", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query("", description="Search by email"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="asc or desc"),
    _admin: str = Depends(get_admin_user),
):
    with get_db() as db:
        query = db.query(User)

        if search:
            query = query.filter(User.email.ilike(f"%{search}%"))

        total = query.count()

        sort_column = getattr(User, sort_by, User.created_at)
        if sort_order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        users = query.offset((page - 1) * page_size).limit(page_size).all()

        user_ids = [u.id for u in users]

        # Batch query book counts
        book_counts = dict(
            db.query(Book.user_id, func.count(Book.id))
            .filter(Book.user_id.in_(user_ids))
            .group_by(Book.user_id)
            .all()
        )

        # Batch query reading totals
        reading_totals = dict(
            db.query(
                ReadingStat.user_id,
                func.coalesce(func.sum(ReadingStat.duration_seconds), 0),
            )
            .filter(ReadingStat.user_id.in_(user_ids))
            .group_by(ReadingStat.user_id)
            .all()
        )

        # Batch query last active time from Redis
        last_active_map: dict[str, str | None] = {}
        if user_ids:
            try:
                r = get_redis()
                keys = [f"{ACTIVE_KEY_PREFIX}{uid}" for uid in user_ids]
                values = r.mget(keys)
                for uid, val in zip(user_ids, values):
                    last_active_map[uid] = val.decode() if val else None
            except Exception:
                pass  # Redis down — last_active will be None

        items = []
        for u in users:
            items.append(
                UserListItem(
                    id=u.id,
                    email=u.email,
                    is_verified=bool(u.is_verified),
                    is_admin=bool(u.is_admin),
                    is_active=bool(u.is_active),
                    created_at=u.created_at.isoformat() if u.created_at else None,
                    last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
                    last_active_at=last_active_map.get(u.id),
                    book_count=book_counts.get(u.id, 0),
                    total_reading_seconds=reading_totals.get(u.id, 0),
                )
            )

        return UserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(user_id: str, _admin: str = Depends(get_admin_user)):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        book_count = db.query(func.count(Book.id)).filter(Book.user_id == user_id).scalar()
        reading_total = (
            db.query(func.coalesce(func.sum(ReadingStat.duration_seconds), 0))
            .filter(ReadingStat.user_id == user_id)
            .scalar()
        )
        highlight_count = db.query(func.count(Highlight.id)).filter(Highlight.user_id == user_id).scalar()

        # Read last active time from Redis
        last_active_at = None
        try:
            r = get_redis()
            val = r.get(f"{ACTIVE_KEY_PREFIX}{user_id}")
            if val:
                last_active_at = val.decode()
        except Exception:
            pass

        return UserDetail(
            id=user.id,
            email=user.email,
            is_verified=bool(user.is_verified),
            is_admin=bool(user.is_admin),
            is_active=bool(user.is_active),
            created_at=user.created_at.isoformat() if user.created_at else None,
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
            last_active_at=last_active_at,
            book_count=book_count,
            total_reading_seconds=reading_total,
            highlight_count=highlight_count,
        )


@router.patch("/{user_id}")
async def update_user(user_id: str, data: UserUpdate, _admin: str = Depends(get_admin_user)):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        if data.is_active is not None:
            user.is_active = data.is_active
        if data.is_admin is not None:
            user.is_admin = data.is_admin

        db.commit()
        return {"message": "更新成功"}


@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_stats(user_id: str, _admin: str = Depends(get_admin_user)):
    with get_db() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        total_books = db.query(func.count(Book.id)).filter(Book.user_id == user_id).scalar()
        total_reading = (
            db.query(func.coalesce(func.sum(ReadingStat.duration_seconds), 0))
            .filter(ReadingStat.user_id == user_id)
            .scalar()
        )
        total_highlights = db.query(func.count(Highlight.id)).filter(Highlight.user_id == user_id).scalar()
        reading_days = (
            db.query(func.count(func.distinct(ReadingStat.date)))
            .filter(ReadingStat.user_id == user_id)
            .scalar()
        )

        recent_books = (
            db.query(Book.id, Book.title, Book.last_opened_at)
            .filter(Book.user_id == user_id)
            .order_by(Book.last_opened_at.desc().nullslast())
            .limit(5)
            .all()
        )

        return UserStats(
            total_books=total_books,
            total_reading_seconds=total_reading,
            total_highlights=total_highlights,
            reading_days=reading_days,
            recent_books=[
                {
                    "id": b.id,
                    "title": b.title,
                    "last_opened_at": b.last_opened_at.isoformat() if b.last_opened_at else None,
                }
                for b in recent_books
            ],
        )
