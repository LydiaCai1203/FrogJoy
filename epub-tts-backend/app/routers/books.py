import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import func, case
from loguru import logger
from app.middleware.auth import get_current_user, get_optional_user, get_admin_user
from shared.database import get_db
from shared.models import Book, ReadingProgress, IndexedBook
from app.services.book_service import BookService
from shared.config import settings
from app.middleware.rate_limit import is_guest_user
from typing import Optional


class VisibilityRequest(BaseModel):
    is_public: bool

router = APIRouter(prefix="/books", tags=["books"])

@router.post("")
async def upload_book(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    if is_guest_user(user_id):
        raise HTTPException(status_code=403, detail="游客账号不允许上传书籍")
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
        logger.error(f"Upload error: {error_detail}")
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

        if user_id and not is_guest_user(user_id):
            query = query.filter(Book.user_id == user_id)
            query = query.order_by(
                case((Book.last_opened_at.is_(None), 1), else_=0),
                Book.last_opened_at.desc(),
            )
        else:
            query = query.filter(Book.is_public == True)
            query = query.order_by(Book.created_at.desc())

        book_rows = query.all()
        if not book_rows:
            return []

        book_ids = [row.id for row in book_rows]

        # 批量读阅读进度 (只查登录用户自己的)
        progress_map: dict = {}
        if user_id:
            rps = db.query(ReadingProgress).filter(
                ReadingProgress.user_id == user_id,
                ReadingProgress.book_id.in_(book_ids),
            ).all()
            for rp in rps:
                chapter_index = rp.chapter_index
                total_chapters = rp.total_chapters
                if chapter_index is not None and total_chapters:
                    percentage = round((chapter_index / total_chapters) * 100, 1)
                else:
                    # 旧数据兼容：没有章节索引时显示 0%
                    percentage = 0.0
                progress_map[rp.book_id] = {
                    "chapterIndex": chapter_index,
                    "totalChapters": total_chapters,
                    "percentage": percentage,
                }

        # 批量读索引+概念状态 (只查登录用户的书)
        index_map: dict = {}
        if user_id:
            index_map = {
                ib.book_id: ib
                for ib in db.query(IndexedBook).filter(
                    IndexedBook.user_id == user_id,
                    IndexedBook.book_id.in_(book_ids),
                ).all()
            }

        # 组装响应
        books = []
        for row in book_rows:
            bid = row.id
            reading_progress = progress_map.get(bid)

            # 索引状态: 只在用户拥有此书时展示按钮
            index_status = None
            if user_id and row.user_id == user_id:
                ib = index_map.get(bid)
                if ib:
                    index_status = {
                        "status": ib.status,
                        "total_chapters": ib.total_chapters,
                        "total_paragraphs": ib.total_paragraphs,
                        "error_message": ib.error_message,
                    }

            # 概念状态
            concept_status = None
            if user_id and row.user_id == user_id:
                ib = index_map.get(bid)
                if ib and ib.concept_status:
                    concept_status = {"concept_status": ib.concept_status}

            books.append({
                "id": bid,
                "title": row.title,
                "creator": row.creator,
                "coverUrl": row.cover_url,
                "isPublic": bool(row.is_public),
                "userId": row.user_id if (user_id and row.user_id == user_id) else None,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
                "lastOpenedAt": row.last_opened_at.isoformat() if row.last_opened_at else None,
                "readingProgress": reading_progress,
                "indexStatus": index_status,
                "conceptStatus": concept_status,
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
            logger.warning(f"Failed to get first chapter: {e}")

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

@router.patch("/{book_id}/visibility")
async def update_visibility(
    book_id: str,
    data: VisibilityRequest,
    user_id: str = Depends(get_admin_user),
):
    with get_db() as db:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(status_code=404, detail="Book not found")
        book.is_public = data.is_public
        db.commit()
    return {"bookId": book_id, "isPublic": data.is_public}


@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    user_id: str = Depends(get_current_user)
):
    logger.info(f"[DeleteBook] Request to delete book_id={book_id}, user_id={user_id}")

    with get_db() as db:
        try:
            book_row = db.query(Book).filter(Book.id == book_id).first()

            if not book_row:
                logger.warning(f"[DeleteBook] Book not found: book_id={book_id}")
                raise HTTPException(status_code=404, detail="Book not found")

            if book_row.user_id != user_id:
                logger.warning(f"[DeleteBook] Access denied: book_id={book_id}, owner={book_row.user_id}, requester={user_id}")
                raise HTTPException(status_code=403, detail="You can only delete your own books")

            # Remove the entire per-book directory
            book_dir = settings.get_user_book_dir(user_id, book_id)
            if os.path.isdir(book_dir):
                shutil.rmtree(book_dir)
            else:
                logger.warning(f"[DeleteBook] Directory not found: {book_dir}")

            db.delete(book_row)
            db.commit()
            logger.info(f"[DeleteBook] Successfully deleted book: book_id={book_id}, title='{book_row.title}'")
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.exception(f"[DeleteBook] Failed to delete book: book_id={book_id}, error={type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Book deleted", "bookId": book_id}
