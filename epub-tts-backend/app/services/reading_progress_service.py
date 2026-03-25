from app.models.database import get_db
from app.models.models import ReadingProgress
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
