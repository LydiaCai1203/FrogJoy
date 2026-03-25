import uuid
from datetime import date, timedelta
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.database import get_db
from app.models.models import ReadingStat, Book


class ReadingStatsService:
    @staticmethod
    def heartbeat(user_id: str, book_id: str, seconds: int) -> None:
        today = date.today().isoformat()
        record_id = str(uuid.uuid4())
        db = next(get_db())
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
        finally:
            db.close()

    @staticmethod
    def get_heatmap(user_id: str, year: int) -> list:
        db = next(get_db())
        try:
            rows = (
                db.query(ReadingStat.date, func.sum(ReadingStat.duration_seconds).label("seconds"))
                .filter(ReadingStat.user_id == user_id, ReadingStat.date.like(f"{year}-%"))
                .group_by(ReadingStat.date)
                .order_by(ReadingStat.date)
                .all()
            )
            return [{"date": r.date, "seconds": r.seconds} for r in rows]
        finally:
            db.close()

    @staticmethod
    def get_book_stats(user_id: str) -> list:
        db = next(get_db())
        try:
            rows = (
                db.query(
                    ReadingStat.book_id,
                    Book.title,
                    Book.cover_url,
                    func.sum(ReadingStat.duration_seconds).label("total_seconds"),
                    func.max(ReadingStat.date).label("last_read_date"),
                )
                .join(Book, Book.id == ReadingStat.book_id)
                .filter(ReadingStat.user_id == user_id)
                .group_by(ReadingStat.book_id, Book.title, Book.cover_url)
                .order_by(func.sum(ReadingStat.duration_seconds).desc())
                .all()
            )
            return [
                {
                    "book_id": r.book_id,
                    "title": r.title,
                    "cover_url": r.cover_url,
                    "total_seconds": r.total_seconds,
                    "last_read_date": r.last_read_date,
                }
                for r in rows
            ]
        finally:
            db.close()

    @staticmethod
    def get_summary(user_id: str) -> dict:
        db = next(get_db())
        try:
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
            dates = {r[0] for r in date_rows}

            streak_days = 0
            check = date.today()
            if check.isoformat() not in dates:
                check = check - timedelta(days=1)
            while check.isoformat() in dates:
                streak_days += 1
                check = check - timedelta(days=1)

            return {
                "total_seconds": total_seconds,
                "books_count": books_count,
                "streak_days": streak_days,
            }
        finally:
            db.close()
