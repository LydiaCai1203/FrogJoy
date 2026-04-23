import uuid
from datetime import date, timedelta
from sqlalchemy import func, extract
from sqlalchemy.dialects.postgresql import insert as pg_insert
from shared.database import get_db
from shared.models import ReadingStat, Book
from app.services.book_service import BookService


class ReadingStatsService:
    @staticmethod
    def heartbeat(user_id: str, book_id: str, seconds: int) -> None:
        today = date.today().isoformat()
        record_id = str(uuid.uuid4())
        with get_db() as db:
            try:
                stmt = pg_insert(ReadingStat).values(
                    id=record_id,
                    user_id=user_id,
                    book_id=book_id,
                    date=today,
                    duration_seconds=seconds,
                ).on_conflict_do_update(
                    constraint="uq_reading_stats_user_book_date",
                    set_={
                        "duration_seconds": ReadingStat.duration_seconds + seconds,
                        "updated_at": func.now(),
                    },
                )
                db.execute(stmt)
                db.commit()
            except Exception:
                db.rollback()
                raise

    @staticmethod
    def get_heatmap(user_id: str, year: int) -> list:
        with get_db() as db:
            rows = (
                db.query(ReadingStat.date, func.sum(ReadingStat.duration_seconds).label("seconds"))
                .filter(ReadingStat.user_id == user_id, extract('year', ReadingStat.date) == year)
                .group_by(ReadingStat.date)
                .order_by(ReadingStat.date)
                .all()
            )
            return [{"date": r.date, "seconds": r.seconds} for r in rows]

    @staticmethod
    def get_book_stats(user_id: str) -> list:
        with get_db() as db:
            rows = (
                db.query(
                    ReadingStat.book_id,
                    Book.title,
                    Book.cover_url,
                    Book.user_id.label("owner_id"),
                    func.sum(ReadingStat.duration_seconds).label("total_seconds"),
                    func.max(ReadingStat.date).label("last_read_date"),
                )
                .join(Book, Book.id == ReadingStat.book_id)
                .filter(ReadingStat.user_id == user_id)
                .group_by(ReadingStat.book_id, Book.title, Book.cover_url, Book.user_id)
                .order_by(func.sum(ReadingStat.duration_seconds).desc())
                .all()
            )
            result = []
            for r in rows:
                cover_url = r.cover_url
                if not cover_url:
                    try:
                        meta_info = BookService.parse_metadata(r.book_id, r.owner_id)
                        cover_url = meta_info.get("coverUrl")
                    except Exception:
                        pass
                result.append({
                    "book_id": r.book_id,
                    "title": r.title,
                    "cover_url": cover_url,
                    "total_seconds": r.total_seconds,
                    "last_read_date": r.last_read_date,
                })
            return result

    @staticmethod
    def get_summary(user_id: str) -> dict:
        with get_db() as db:
            total_seconds = (
                db.query(func.sum(ReadingStat.duration_seconds))
                .filter(ReadingStat.user_id == user_id)
                .scalar()
            ) or 0

            books_count = (
                db.query(func.count(ReadingStat.book_id.distinct()))
                .filter(ReadingStat.user_id == user_id)
                .scalar()
            ) or 0

            date_rows = (
                db.query(ReadingStat.date.distinct())
                .filter(ReadingStat.user_id == user_id)
                .all()
            )
            dates = {r[0] if isinstance(r[0], date) else date.fromisoformat(str(r[0])) for r in date_rows}

            streak_days = 0
            check = date.today()
            if check not in dates:
                check = check - timedelta(days=1)
            while check in dates:
                streak_days += 1
                check = check - timedelta(days=1)

            return {
                "total_seconds": total_seconds,
                "books_count": books_count,
                "streak_days": streak_days,
            }
