"""
AI translation routes: chapter translation, book translation, get translations.
"""
import asyncio
import json
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse

from shared.schemas.ai import TranslateChapterRequest, TranslateBookRequest
from shared.models import BookTranslation, UserPreferences
from shared.database import get_db
from shared.config import settings
from app.deps import get_book_owner, get_book_title
from app.services.ai.provider import AIService
from app.services.ai.translation import run_book_translation
from app.services.task_service import task_manager
from app.routers.ai_config import _build_ai_config, _load_ai_prefs
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import check_guest_rate_limit

router = APIRouter(prefix="/ai", tags=["ai-translate"])


def _get_translation_prompt(user_id: str, target_lang: str) -> str:
    prefs = _load_ai_prefs(user_id)
    if prefs and prefs.translation_prompt:
        return prefs.translation_prompt
    return (
        f"You are a professional translator. Translate the following text to {target_lang}. "
        "Keep the original meaning, tone, and formatting. "
        "Only output the translation, no explanations or commentary."
    )


@router.post("/translate/chapter")
async def translate_chapter(request: TranslateChapterRequest, user_id: str = Depends(get_current_user)):
    """Translate a single chapter as SSE stream, sentence by sentence."""
    check_guest_rate_limit(user_id, "translate")
    # Verify book access
    get_book_owner(request.book_id, user_id)
    ai_config = _build_ai_config(user_id, config_type="translation")
    service = AIService(ai_config)

    sentences = [s.strip() for s in request.sentences if s.strip()]
    if not sentences:
        return StreamingResponse(iter([]), media_type="text/event-stream")

    total = len(sentences)

    async def generate():
        translated_parts = []
        custom_prompt = _get_translation_prompt(user_id, request.target_lang)
        for i, sentence in enumerate(sentences):
            try:
                messages = AIService.build_translation_messages(sentence, request.target_lang, custom_prompt)
                result = await service.chat_once(messages, temperature=0.3, max_tokens=2048)
                translated_parts.append(result.strip())
            except Exception as e:
                translated_parts.append(sentence)  # fallback: keep original
            progress = int((i + 1) / total * 100)
            payload = json.dumps({
                "progress": progress,
                "index": i,
                "total": total,
                "translated_part": translated_parts[-1],
                "done": (i + 1) == total,
                "full_translated": " ".join(translated_parts) if (i + 1) == total else "",
            }, ensure_ascii=False)
            yield f"data: {payload}\n\n"

        # Persist translated pairs to file
        try:
            file_path = settings.get_translation_path(user_id, request.book_id, request.target_lang, request.chapter_href)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            pairs = [
                {"original": s, "translated": t}
                for s, t in zip(sentences, translated_parts)
            ]
            data = {
                "chapter_href": request.chapter_href,
                "target_lang": request.target_lang,
                "pairs": pairs,
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            import traceback
            traceback.print_exc()

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/translate/book")
async def translate_book(request: TranslateBookRequest, user_id: str = Depends(get_current_user)):
    """Start an async whole-book translation task."""
    # Verify book access
    owner_id = get_book_owner(request.book_id, user_id)
    book_title = get_book_title(request.book_id, user_id)

    ai_config = _build_ai_config(user_id, config_type="translation")
    custom_prompt = _get_translation_prompt(user_id, "Chinese")

    task_id = task_manager.create_task(
        task_type="book_translation",
        params={"book_id": request.book_id, "mode": request.mode},
        title=f"翻译《{book_title}》",
        user_id=user_id,
    )

    asyncio.create_task(run_book_translation(
        task_id=task_id,
        book_id=request.book_id,
        owner_id=owner_id,
        user_id=user_id,
        mode=request.mode,
        ai_config=ai_config,
        custom_prompt=custom_prompt,
    ))

    return {"task_id": task_id, "message": f"开始翻译《{book_title}》"}


@router.get("/translate/{book_id}/chapter")
async def get_chapter_translation(
    book_id: str,
    chapter_href: str = Query(..., description="Chapter href"),
    target_lang: str = Query(default="Chinese", description="Target language"),
    user_id: str = Depends(get_current_user),
):
    """Get saved translation for a single chapter from file."""
    file_path = settings.get_translation_path(user_id, book_id, target_lang, chapter_href)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="No translation found")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        raise HTTPException(status_code=404, detail="No translation found")


@router.get("/translate/{book_id}")
async def get_book_translations(book_id: str, user_id: str = Depends(get_current_user)):
    """Get all translation results for a book."""
    with get_db() as db:
        rows = db.query(BookTranslation).filter(
            BookTranslation.user_id == user_id,
            BookTranslation.book_id == book_id,
        ).all()
    return [
        {
            "chapter_href": r.chapter_href,
            "translated_content": r.translated_content,
            "status": r.status,
            "error_message": r.error_message,
        }
        for r in rows
    ]
