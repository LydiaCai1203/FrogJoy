import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy import func, case
from loguru import logger
from app.middleware.auth import get_current_user, get_optional_user
from app.models.database import get_db
from app.models.models import Book
from app.services.book_service import BookService
from app.services.reading_progress_service import ReadingProgressService
from app.config import settings
from typing import Optional

router = APIRouter(prefix="/books", tags=["books"])

@router.post("")
async def upload_book(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    if not file.filename.endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only EPUB files are supported")

    book_id = None
    try:
        book_id, file_path = await BookService.save_upload(file, user_id)

        try:
            meta_info = BookService.parse_metadata(book_id, user_id)
        except HTTPException as e:
            if book_id:
                book_dir = settings.get_user_book_dir(user_id, book_id)
                if os.path.isdir(book_dir):
                    shutil.rmtree(book_dir)
            raise e

        try:
            toc = BookService.get_toc(book_id, user_id)
        except HTTPException as e:
            if book_id:
                book_dir = settings.get_user_book_dir(user_id, book_id)
                if os.path.isdir(book_dir):
                    shutil.rmtree(book_dir)
            raise e

        cover_url = meta_info["coverUrl"]

        with get_db() as db:
            try:
                book = Book(
                    id=book_id,
                    user_id=user_id,
                    title=meta_info["metadata"].get("title", "Unknown"),
                    creator=meta_info["metadata"].get("creator", "Unknown"),
                    cover_url=cover_url,
                    file_path=file_path,
                    is_public=False,
                )
                db.add(book)
                db.commit()
            except Exception:
                db.rollback()
                raise

        return {
            "bookId": book_id,
            "metadata": meta_info["metadata"],
            "coverUrl": cover_url,
            "toc": toc
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Unexpected error: {str(e)}"
        print(f"Upload error: {error_detail}")
        traceback.print_exc()
        if book_id:
            book_dir = settings.get_user_book_dir(user_id, book_id)
            if os.path.isdir(book_dir):
                shutil.rmtree(book_dir)
        raise HTTPException(status_code=500, detail=error_detail)

@router.get("")
async def list_books(user_id: Optional[str] = Depends(get_optional_user)):
    with get_db() as db:
        query = db.query(Book)

        if user_id:
            query = query.filter((Book.user_id == user_id) | (Book.is_public == True))
            query = query.order_by(
                case((Book.last_opened_at.is_(None), 1), else_=0),
                Book.last_opened_at.desc(),
            )
        else:
            query = query.filter(Book.is_public == True)
            query = query.order_by(Book.created_at.desc())

        books = []
        for row in query.all():
            cover_url = row.cover_url
            if not cover_url:
                try:
                    meta_info = BookService.parse_metadata(row.id, row.user_id)
                    cover_url = meta_info.get("coverUrl")
                except Exception:
                    pass

            reading_progress = None
            if user_id:
                try:
                    reading_progress = ReadingProgressService.get_progress_with_percentage(
                        user_id, row.id, row.user_id
                    )
                except Exception:
                    pass

            books.append({
                "id": row.id,
                "title": row.title,
                "creator": row.creator,
                "coverUrl": cover_url,
                "isPublic": bool(row.is_public),
                "userId": row.user_id,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
                "lastOpenedAt": row.last_opened_at.isoformat() if row.last_opened_at else None,
                "readingProgress": reading_progress,
            })

        return books

@router.get("/{book_id}")
async def get_book(
    book_id: str,
    user_id: Optional[str] = Depends(get_optional_user)
):
    with get_db() as db:
        try:
            book_row = db.query(Book).filter(Book.id == book_id).first()

            if not book_row:
                raise HTTPException(status_code=404, detail="Book not found")

            if not book_row.is_public and book_row.user_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied")

            owner_id = book_row.user_id

            book_path = BookService.get_book_path(owner_id, book_id)
            if not os.path.exists(book_path):
                raise HTTPException(status_code=404, detail="Book file not found")

            book_row.last_opened_at = func.now()
            db.commit()
        except HTTPException:
            raise
        except Exception:
            db.rollback()
            raise

    try:
        meta_info = BookService.parse_metadata(book_id, owner_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse metadata: {str(e)}")

    try:
        toc = BookService.get_toc(book_id, owner_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        toc = []

    if not toc:
        try:
            first_chapter = BookService.get_first_available_chapter(book_id, owner_id)
            if first_chapter:
                toc = [first_chapter]
        except Exception as e:
            print(f"Warning: Failed to get first chapter: {e}")

    return {
        "bookId": book_id,
        "metadata": meta_info["metadata"],
        "coverUrl": meta_info["coverUrl"],
        "toc": toc
    }

@router.get("/{book_id}/chapters")
async def get_chapter(
    book_id: str,
    href: str,
    user_id: Optional[str] = Depends(get_optional_user)
):
    with get_db() as db:
        book_row = db.query(Book).filter(Book.id == book_id).first()

        if not book_row:
            raise HTTPException(status_code=404, detail="Book not found")

        if not book_row.is_public and book_row.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        owner_id = book_row.user_id

    try:
        chapter_content = BookService.get_chapter_content(book_id, href, owner_id)
        return chapter_content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chapter: {str(e)}")

@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    user_id: str = Depends(get_current_user)
):
    with get_db() as db:
        try:
            book_row = db.query(Book).filter(Book.id == book_id).first()

            if not book_row:
                raise HTTPException(status_code=404, detail="Book not found")

            if book_row.user_id != user_id:
                raise HTTPException(status_code=403, detail="You can only delete your own books")

            # Remove the entire per-book directory
            book_dir = settings.get_user_book_dir(user_id, book_id)
            if os.path.isdir(book_dir):
                logger.info(f"Deleting book directory: {book_dir}")
                shutil.rmtree(book_dir)

            logger.info(f"Deleting book record from database: {book_id}")
            db.delete(book_row)
            db.commit()
            logger.info(f"Book {book_id} deleted successfully")
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            import traceback
            logger.error(f"Error deleting book {book_id}: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Book deleted", "bookId": book_id}
