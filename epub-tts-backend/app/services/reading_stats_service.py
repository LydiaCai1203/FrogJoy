import uuid
from datetime import date, timedelta
from app.models.database import get_db


class ReadingStatsService:
    @staticmethod
    def heartbeat(user_id: str, book_id: str, seconds: int) -> None:
        today = date.today().isoformat()
        record_id = str(uuid.uuid4())
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO reading_stats (id, user_id, book_id, date, duration_seconds) VALUES (?, ?, ?, ?, 0)",
                (record_id, user_id, book_id, today),
            )
            cursor.execute(
                """UPDATE reading_stats
                   SET duration_seconds = duration_seconds + ?, updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ? AND book_id = ? AND date = ?""",
                (seconds, user_id, book_id, today),
            )

    @staticmethod
    def get_heatmap(user_id: str, year: int) -> list:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT date, SUM(duration_seconds) as seconds
                   FROM reading_stats
                   WHERE user_id = ? AND date LIKE ?
                   GROUP BY date
                   ORDER BY date""",
                (user_id, f"{year}-%"),
            )
            return [{"date": row["date"], "seconds": row["seconds"]} for row in cursor.fetchall()]

    @staticmethod
    def get_book_stats(user_id: str) -> list:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT rs.book_id, b.title, b.cover_url,
                          SUM(rs.duration_seconds) as total_seconds,
                          MAX(rs.date) as last_read_date
                   FROM reading_stats rs
                   JOIN books b ON b.id = rs.book_id
                   WHERE rs.user_id = ?
                   GROUP BY rs.book_id
                   ORDER BY total_seconds DESC""",
                (user_id,),
            )
            return [
                {
                    "book_id": row["book_id"],
                    "title": row["title"],
                    "cover_url": row["cover_url"],
                    "total_seconds": row["total_seconds"],
                    "last_read_date": row["last_read_date"],
                }
                for row in cursor.fetchall()
            ]

    @staticmethod
    def get_summary(user_id: str) -> dict:
        with get_db() as conn:
            cursor = conn.cursor()

            # Total seconds
            cursor.execute(
                "SELECT SUM(duration_seconds) as total FROM reading_stats WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            total_seconds = row["total"] or 0

            # Books count
            cursor.execute(
                "SELECT COUNT(DISTINCT book_id) as cnt FROM reading_stats WHERE user_id = ?",
                (user_id,),
            )
            books_count = cursor.fetchone()["cnt"]

            # Streak: count consecutive days ending today or yesterday
            cursor.execute(
                """SELECT DISTINCT date FROM reading_stats
                   WHERE user_id = ?
                   ORDER BY date DESC""",
                (user_id,),
            )
            dates = {row["date"] for row in cursor.fetchall()}

            streak_days = 0
            check = date.today()
            # Allow streak starting from yesterday if nothing today
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
