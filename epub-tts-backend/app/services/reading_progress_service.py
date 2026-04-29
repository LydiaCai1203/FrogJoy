import logging
from typing import Dict, Any, List, Optional
from shared.database import get_db
from shared.models import ReadingProgress
from sqlalchemy.dialects.postgresql import insert as pg_insert

logger = logging.getLogger(__name__)


class ReadingProgressService:
    @staticmethod
    def get(user_id: str, book_id: str) -> dict | None:
        with get_db() as db:
            row = db.query(ReadingProgress).filter_by(
                user_id=user_id, book_id=book_id
            ).first()
            if row is None:
                return None
            return {
                "chapter_href": row.chapter_href,
                "paragraph_index": row.paragraph_index,
                "chapter_index": row.chapter_index,
                "total_chapters": row.total_chapters,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }

    @staticmethod
    def get_progress_with_percentage(user_id: str, book_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
        progress = ReadingProgressService.get(user_id, book_id)
        if progress is None:
            return None

        chapter_index = progress.get("chapter_index")
        total_chapters = progress.get("total_chapters")
        if chapter_index is None or not total_chapters:
            return None

        percentage = round((chapter_index / total_chapters) * 100, 1)
        return {
            "chapterIndex": chapter_index,
            "totalChapters": total_chapters,
            "percentage": percentage,
        }

    @staticmethod
    def save(
        user_id: str,
        book_id: str,
        chapter_href: str,
        paragraph_index: int,
        chapter_index: int | None = None,
        total_chapters: int | None = None,
    ) -> None:
        from sqlalchemy import func
        with get_db() as db:
            try:
                values = {
                    "user_id": user_id,
                    "book_id": book_id,
                    "chapter_href": chapter_href,
                    "paragraph_index": paragraph_index,
                    "chapter_index": chapter_index,
                    "total_chapters": total_chapters,
                    "updated_at": func.now(),
                }
                stmt = pg_insert(ReadingProgress).values(**values).on_conflict_do_update(
                    index_elements=["user_id", "book_id"],
                    set_={
                        "chapter_href": chapter_href,
                        "paragraph_index": paragraph_index,
                        "chapter_index": chapter_index,
                        "total_chapters": total_chapters,
                        "updated_at": func.now(),
                    },
                )
                db.execute(stmt)
                db.commit()
            except Exception:
                db.rollback()
                raise
