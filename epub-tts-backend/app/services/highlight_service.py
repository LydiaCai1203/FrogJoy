import uuid
from app.models.database import get_db


class HighlightService:
    @staticmethod
    def list_by_chapter(book_id: str, chapter_href: str, user_id: str) -> list[dict]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, book_id, chapter_href, paragraph_index, end_paragraph_index,
                       start_offset, end_offset, selected_text, color, note, created_at, updated_at
                FROM highlights
                WHERE book_id = ? AND chapter_href = ? AND user_id = ?
                ORDER BY paragraph_index, start_offset
            """, (book_id, chapter_href, user_id))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def list_by_book(book_id: str, user_id: str) -> list[dict]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, book_id, chapter_href, paragraph_index, end_paragraph_index,
                       start_offset, end_offset, selected_text, color, note, created_at, updated_at
                FROM highlights
                WHERE book_id = ? AND user_id = ?
                ORDER BY chapter_href, paragraph_index, start_offset
            """, (book_id, user_id))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def create(
        user_id: str,
        book_id: str,
        chapter_href: str,
        paragraph_index: int,
        end_paragraph_index: int,
        start_offset: int,
        end_offset: int,
        selected_text: str,
        color: str,
        note: str | None,
    ) -> dict:
        highlight_id = str(uuid.uuid4())
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO highlights (
                    id, user_id, book_id, chapter_href, paragraph_index, end_paragraph_index,
                    start_offset, end_offset, selected_text, color, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                highlight_id, user_id, book_id, chapter_href,
                paragraph_index, end_paragraph_index,
                start_offset, end_offset, selected_text, color, note
            ))
            cursor.execute("""
                SELECT id, user_id, book_id, chapter_href, paragraph_index, end_paragraph_index,
                       start_offset, end_offset, selected_text, color, note, created_at, updated_at
                FROM highlights WHERE id = ?
            """, (highlight_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def update(highlight_id: str, user_id: str, color: str | None = None, note: str | None = None) -> dict:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id FROM highlights WHERE id = ?", (highlight_id,))
            row = cursor.fetchone()
            if not row:
                return None
            if row["user_id"] != user_id:
                return None

            fields = []
            values = []
            if color is not None:
                fields.append("color = ?")
                values.append(color)
            if note is not None:
                fields.append("note = ?")
                values.append(note)
            if not fields:
                cursor.execute("""
                    SELECT id, user_id, book_id, chapter_href, paragraph_index, end_paragraph_index,
                           start_offset, end_offset, selected_text, color, note, created_at, updated_at
                    FROM highlights WHERE id = ?
                """, (highlight_id,))
                return dict(cursor.fetchone())

            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(highlight_id)
            cursor.execute(f"UPDATE highlights SET {', '.join(fields)} WHERE id = ?", values)
            cursor.execute("""
                SELECT id, user_id, book_id, chapter_href, paragraph_index, end_paragraph_index,
                       start_offset, end_offset, selected_text, color, note, created_at, updated_at
                FROM highlights WHERE id = ?
            """, (highlight_id,))
            return dict(cursor.fetchone())

    @staticmethod
    def delete(highlight_id: str, user_id: str) -> bool:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM highlights WHERE id = ?", (highlight_id,))
            row = cursor.fetchone()
            if not row or row["user_id"] != user_id:
                return False
            cursor.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
            return True

    @staticmethod
    def search(book_id: str, user_id: str, query: str) -> list[dict]:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, user_id, book_id, chapter_href, paragraph_index, end_paragraph_index,
                       start_offset, end_offset, selected_text, color, note, created_at, updated_at
                FROM highlights
                WHERE book_id = ? AND user_id = ? AND (selected_text LIKE ? OR note LIKE ?)
                ORDER BY chapter_href, paragraph_index, start_offset
            """, (book_id, user_id, f"%{query}%", f"%{query}%"))
            return [dict(row) for row in cursor.fetchall()]
