from app.models.database import get_db


class ReadingProgressService:
    @staticmethod
    def get(user_id: str, book_id: str) -> dict | None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT chapter_href, paragraph_index, updated_at
                   FROM reading_progress
                   WHERE user_id = ? AND book_id = ?""",
                (user_id, book_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "chapter_href": row["chapter_href"],
                "paragraph_index": row["paragraph_index"],
                "updated_at": row["updated_at"],
            }

    @staticmethod
    def save(user_id: str, book_id: str, chapter_href: str, paragraph_index: int) -> None:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT OR REPLACE INTO reading_progress
                   (user_id, book_id, chapter_href, paragraph_index, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (user_id, book_id, chapter_href, paragraph_index),
            )
