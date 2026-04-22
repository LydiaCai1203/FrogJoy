from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.middleware.auth import get_current_user
from app.services.highlight_service import HighlightService

router = APIRouter(prefix="/highlights", tags=["highlights"])


class CreateHighlightRequest(BaseModel):
    book_id: str
    chapter_href: str
    paragraph_index: int
    end_paragraph_index: int
    start_offset: int
    end_offset: int
    selected_text: str
    color: str = "yellow"
    note: Optional[str] = None


class UpdateHighlightRequest(BaseModel):
    color: Optional[str] = None
    note: Optional[str] = None


@router.get("")
async def list_highlights(
    book_id: str,
    chapter_href: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    if chapter_href:
        return HighlightService.list_by_chapter(book_id, chapter_href, user_id)
    return HighlightService.list_by_book(book_id, user_id)


@router.post("")
async def create_highlight(
    req: CreateHighlightRequest,
    user_id: str = Depends(get_current_user),
):
    return HighlightService.create(
        user_id=user_id,
        book_id=req.book_id,
        chapter_href=req.chapter_href,
        paragraph_index=req.paragraph_index,
        end_paragraph_index=req.end_paragraph_index,
        start_offset=req.start_offset,
        end_offset=req.end_offset,
        selected_text=req.selected_text,
        color=req.color,
        note=req.note,
    )


@router.get("/search")
async def search_highlights(
    book_id: str,
    q: str,
    user_id: str = Depends(get_current_user),
):
    return HighlightService.search(book_id, user_id, q)


@router.put("/{highlight_id}")
async def update_highlight(
    highlight_id: str,
    req: UpdateHighlightRequest,
    user_id: str = Depends(get_current_user),
):
    result = HighlightService.update(highlight_id, user_id, req.color, req.note)
    if result is None:
        raise HTTPException(status_code=404, detail="Highlight not found or access denied")
    return result


@router.delete("/chapter")
async def delete_chapter_highlights(
    book_id: str,
    chapter_href: str,
    user_id: str = Depends(get_current_user),
):
    count = HighlightService.delete_by_chapter(book_id, chapter_href, user_id)
    return {"message": "Deleted", "count": count}


@router.delete("/{highlight_id}")
async def delete_highlight(
    highlight_id: str,
    user_id: str = Depends(get_current_user),
):
    success = HighlightService.delete(highlight_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Highlight not found or access denied")
    return {"message": "Deleted", "id": highlight_id}
