"""
Background task function for book translation.
Extracted from app/routers/ai.py's _run_book_translation function.
"""
import asyncio
import uuid
from loguru import logger

from app.models.database import get_db
from app.models.models import BookTranslation
from app.services.ai.provider import AIService, AIConfig
from app.services.book_service import BookService
from app.services.task_service import task_manager


async def run_book_translation(
    task_id: str,
    book_id: str,
    owner_id: str,
    user_id: str,
    mode: str,
    ai_config: AIConfig,
    custom_prompt: str,
):
    """Background task: translate all chapters of a book."""
    try:
        task_manager.start_task(task_id)
        service = AIService(ai_config)

        # Get TOC
        toc = BookService.get_toc(book_id, owner_id)
        chapters = []
        def collect(items):
            for item in items:
                chapters.append({"href": item.get("href", ""), "label": item.get("label", "")})
                if item.get("subitems"):
                    collect(item["subitems"])
        collect(toc)

        total = len(chapters)
        if total == 0:
            task_manager.fail_task(task_id, "书籍无章节")
            return

        task_manager.update_progress(task_id, 2, f"共 {total} 章，开始翻译...")

        for i, ch in enumerate(chapters):
            href = ch["href"]
            task_manager.update_progress(task_id, int((i / total) * 90), f"翻译第 {i+1}/{total} 章...")

            try:
                chapter_data = BookService.get_chapter_content(book_id, href, owner_id)
                sentences = chapter_data.get("sentences", [])
                if not sentences:
                    continue
                text = " ".join(sentences)

                translated = await service.chat_once(
                    AIService.build_translation_messages(text, "Chinese", custom_prompt),
                    temperature=0.3,
                    max_tokens=8192,
                )

                # Save translation to DB
                with get_db() as db:
                    existing = db.query(BookTranslation).filter(
                        BookTranslation.user_id == user_id,
                        BookTranslation.book_id == book_id,
                        BookTranslation.chapter_href == href,
                    ).first()
                    if existing:
                        existing.translated_content = translated
                        existing.status = "completed"
                    else:
                        db.add(BookTranslation(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            book_id=book_id,
                            chapter_href=href,
                            original_content=text,
                            translated_content=translated,
                            status="completed",
                        ))
                    db.commit()

            except Exception as e:
                with get_db() as db:
                    existing = db.query(BookTranslation).filter(
                        BookTranslation.user_id == user_id,
                        BookTranslation.book_id == book_id,
                        BookTranslation.chapter_href == href,
                    ).first()
                    if existing:
                        existing.status = "failed"
                        existing.error_message = str(e)
                    else:
                        db.add(BookTranslation(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            book_id=book_id,
                            chapter_href=href,
                            status="failed",
                            error_message=str(e),
                        ))
                    db.commit()

        task_manager.complete_task(task_id, {"book_id": book_id, "total_chapters": total})

    except asyncio.CancelledError:
        task_manager.fail_task(task_id, "任务已取消")
    except Exception as e:
        import traceback
        traceback.print_exc()
        task_manager.fail_task(task_id, str(e))
    finally:
        task_manager.unregister_running_task(task_id)
