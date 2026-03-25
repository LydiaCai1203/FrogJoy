import uuid
from sqlalchemy import func
from app.models.database import get_db
from app.models.models import Highlight


def _highlight_to_dict(h: Highlight) -> dict:
    return {
        "id": h.id,
        "user_id": h.user_id,
        "book_id": h.book_id,
        "chapter_href": h.chapter_href,
        "paragraph_index": h.paragraph_index,
        "end_paragraph_index": h.end_paragraph_index,
        "start_offset": h.start_offset,
        "end_offset": h.end_offset,
        "selected_text": h.selected_text,
        "color": h.color,
        "note": h.note,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "updated_at": h.updated_at.isoformat() if h.updated_at else None,
    }


class HighlightService:
    @staticmethod
    def list_by_chapter(book_id: str, chapter_href: str, user_id: str) -> list[dict]:
        db = next(get_db())
        try:
            rows = (
                db.query(Highlight)
                .filter_by(book_id=book_id, chapter_href=chapter_href, user_id=user_id)
                .order_by(Highlight.paragraph_index, Highlight.start_offset)
                .all()
            )
            return [_highlight_to_dict(r) for r in rows]
        finally:
            db.close()

    @staticmethod
    def list_by_book(book_id: str, user_id: str) -> list[dict]:
        db = next(get_db())
        try:
            rows = (
                db.query(Highlight)
                .filter_by(book_id=book_id, user_id=user_id)
                .order_by(Highlight.chapter_href, Highlight.paragraph_index, Highlight.start_offset)
                .all()
            )
            return [_highlight_to_dict(r) for r in rows]
        finally:
            db.close()

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
        db = next(get_db())
        try:
            h = Highlight(
                id=highlight_id,
                user_id=user_id,
                book_id=book_id,
                chapter_href=chapter_href,
                paragraph_index=paragraph_index,
                end_paragraph_index=end_paragraph_index,
                start_offset=start_offset,
                end_offset=end_offset,
                selected_text=selected_text,
                color=color,
                note=note,
            )
            db.add(h)
            db.commit()
            db.refresh(h)
            return _highlight_to_dict(h)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def update(highlight_id: str, user_id: str, color: str | None = None, note: str | None = None) -> dict:
        db = next(get_db())
        try:
            h = db.query(Highlight).filter_by(id=highlight_id).first()
            if not h or h.user_id != user_id:
                return None

            if color is not None:
                h.color = color
            if note is not None:
                h.note = note
            if color is not None or note is not None:
                h.updated_at = func.now()

            db.commit()
            db.refresh(h)
            return _highlight_to_dict(h)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def delete(highlight_id: str, user_id: str) -> bool:
        db = next(get_db())
        try:
            h = db.query(Highlight).filter_by(id=highlight_id).first()
            if not h or h.user_id != user_id:
                return False
            db.delete(h)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def search(book_id: str, user_id: str, query: str) -> list[dict]:
        db = next(get_db())
        try:
            pattern = f"%{query}%"
            rows = (
                db.query(Highlight)
                .filter(
                    Highlight.book_id == book_id,
                    Highlight.user_id == user_id,
                    (Highlight.selected_text.ilike(pattern) | Highlight.note.ilike(pattern)),
                )
                .order_by(Highlight.chapter_href, Highlight.paragraph_index, Highlight.start_offset)
                .all()
            )
            return [_highlight_to_dict(r) for r in rows]
        finally:
            db.close()
