from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.middleware.auth import get_current_user, get_optional_user
from app.models.database import get_db
from app.services.book_service import BookService, BookLibrary
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
        book_id = await BookService.save_upload(file)
        
        try:
            meta_info = BookService.parse_metadata(book_id)
        except HTTPException as e:
            if book_id:
                book_path = BookService.get_book_path(book_id)
                if os.path.exists(book_path):
                    os.remove(book_path)
            raise e
        
        try:
            toc = BookService.get_toc(book_id)
        except HTTPException as e:
            if book_id:
                book_path = BookService.get_book_path(book_id)
                if os.path.exists(book_path):
                    os.remove(book_path)
            raise e
        
        cover_url = meta_info["coverUrl"]
        
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO books (id, user_id, title, creator, cover_url, file_path, is_public)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (
                book_id,
                user_id,
                meta_info["metadata"].get("title", "Unknown"),
                meta_info["metadata"].get("creator", "Unknown"),
                cover_url,
                BookService.get_book_path(book_id)
            ))
        
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
            book_path = BookService.get_book_path(book_id)
            if os.path.exists(book_path):
                os.remove(book_path)
        raise HTTPException(status_code=500, detail=error_detail)

@router.get("")
async def list_books(user_id: Optional[str] = Depends(get_optional_user)):
    with get_db() as conn:
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT id, title, creator, cover_url, is_public, user_id, created_at, last_opened_at
                FROM books
                WHERE user_id = ? OR is_public = 1
                ORDER BY last_opened_at DESC NULL LAST, created_at DESC
            """, (user_id,))
        else:
            cursor.execute("""
                SELECT id, title, creator, cover_url, is_public, user_id, created_at, last_opened_at
                FROM books
                WHERE is_public = 1
                ORDER BY created_at DESC
            """)
        
        books = []
        for row in cursor.fetchall():
            books.append({
                "id": row["id"],
                "title": row["title"],
                "creator": row["creator"],
                "coverUrl": row["cover_url"],
                "isPublic": bool(row["is_public"]),
                "userId": row["user_id"],
                "createdAt": row["created_at"],
                "lastOpenedAt": row["last_opened_at"]
            })
        
        return books

@router.get("/{book_id}")
async def get_book(
    book_id: str,
    user_id: Optional[str] = Depends(get_optional_user)
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, is_public FROM books WHERE id = ?
        """, (book_id,))
        book_row = cursor.fetchone()
    
    if not book_row:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if not book_row["is_public"] and book_row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    book_path = BookService.get_book_path(book_id)
    if not os.path.exists(book_path):
        raise HTTPException(status_code=404, detail="Book file not found")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE books SET last_opened_at = CURRENT_TIMESTAMP WHERE id = ?
        """, (book_id,))
    
    try:
        meta_info = BookService.parse_metadata(book_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse metadata: {str(e)}")
    
    try:
        toc = BookService.get_toc(book_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        toc = []
    
    if not toc:
        try:
            first_chapter = BookService.get_first_available_chapter(book_id)
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

@router.delete("/{book_id}")
async def delete_book(
    book_id: str,
    user_id: str = Depends(get_current_user)
):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM books WHERE id = ?", (book_id,))
        book_row = cursor.fetchone()
    
    if not book_row:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if book_row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only delete your own books")
    
    book_path = BookService.get_book_path(book_id)
    if os.path.exists(book_path):
        os.remove(book_path)
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
    
    return {"message": "Book deleted", "bookId": book_id}

import os
