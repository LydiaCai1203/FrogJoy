from typing import Dict, Any, List, Optional
from app.models.database import get_db
from app.models.models import ReadingProgress
from app.services.book_service import BookService
from sqlalchemy.dialects.postgresql import insert as pg_insert


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
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }

    @staticmethod
    def get_progress_with_percentage(user_id: str, book_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
        progress = ReadingProgressService.get(user_id, book_id)
        if progress is None:
            return None

        try:
            toc = BookService.get_toc(book_id, owner_id)
            flat_toc = BookService.flatten_toc(toc)
            total_chapters = len(flat_toc)

            if total_chapters == 0:
                return None

            chapter_index = 0
            for i, item in enumerate(flat_toc):
                if item["href"] == progress["chapter_href"]:
                    chapter_index = i
                    break

            percentage = round((chapter_index / total_chapters) * 100, 1)
            return {
                "chapterIndex": chapter_index,
                "totalChapters": total_chapters,
                "percentage": percentage,
            }
        except Exception:
            return None

    @staticmethod
    def save(user_id: str, book_id: str, chapter_href: str, paragraph_index: int) -> None:
        from sqlalchemy import func
        with get_db() as db:
            try:
                stmt = pg_insert(ReadingProgress).values(
                    user_id=user_id,
                    book_id=book_id,
                    chapter_href=chapter_href,
                    paragraph_index=paragraph_index,
                    updated_at=func.now(),
                ).on_conflict_do_update(
                    index_elements=["user_id", "book_id"],
                    set_={
                        "chapter_href": chapter_href,
                        "paragraph_index": paragraph_index,
                        "updated_at": func.now(),
                    },
                )
                db.execute(stmt)
                db.commit()
            except Exception:
                db.rollback()
                raise
