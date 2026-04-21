"""
TTS download routes: chapter download, smart chapter download, book audio, book zip, file serving.
"""
import asyncio
import os
import time as time_module
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from loguru import logger

from shared.schemas.tts import DownloadRequest, ChapterDownloadRequest, BookDownloadRequest, BookDownloadZipRequest
from shared.models import Book
from shared.database import get_db
from shared.config import settings
from app.deps import get_book_owner
from app.services.book_service import BookService
from app.services.tts.facade import TTSFacade as TTSService
from app.services.tts.download import generate_book_audio_task, generate_book_audio_zip_task
from app.services.task_service import task_manager, TaskStatus
from app.middleware.auth import get_current_user

router = APIRouter(tags=["tts-download"])


@router.post("/tts/download/chapter")
async def download_chapter_audio(request: DownloadRequest, user_id: str = Depends(get_current_user)):
    if not request.sentences or len(request.sentences) == 0:
        raise HTTPException(status_code=400, detail="No sentences provided")

    sentences = [s.strip() for s in request.sentences if s and s.strip()]
    if not sentences:
        raise HTTPException(status_code=400, detail="All sentences are empty")

    logger.debug(f"[API] Download request: {len(sentences)} sentences, voice={request.voice}")

    try:
        full_text = "\n".join(sentences)

        result = await TTSService.generate_chapter_audio(
            text=full_text,
            voice=request.voice,
            rate=request.rate,
            pitch=request.pitch,
            filename=request.filename,
            user_id=user_id
        )

        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tts/download/chapter/smart")
async def download_chapter_audio_smart(request: ChapterDownloadRequest, user_id: str = Depends(get_current_user)):
    owner_id = get_book_owner(request.book_id, user_id)

    try:
        chapter = BookService.get_chapter_content(request.book_id, request.chapter_href, owner_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Chapter not found: {e}")

    sentences = chapter.get("sentences", [])
    if not sentences:
        raise HTTPException(status_code=400, detail="Chapter has no content")

    logger.debug(f"[API] Smart download: book={request.book_id}, chapter={request.chapter_href}, {len(sentences)} paragraphs")

    try:
        result = await TTSService.generate_chapter_audio_smart(
            book_id=request.book_id,
            chapter_href=request.chapter_href,
            sentences=sentences,
            voice=request.voice,
            rate=request.rate,
            pitch=request.pitch,
            filename=request.filename,
            user_id=user_id
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/audio/{book_id}/{filename}")
async def get_download_file(book_id: str, filename: str, user_id: str = Depends(get_current_user)):
    """Serve a generated audio/zip file for download from the per-book audio dir."""
    audio_dir = settings.get_audio_dir(user_id, book_id)
    filepath = os.path.join(audio_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    if filename.endswith(".zip"):
        media_type = "application/zip"
    else:
        media_type = "audio/mpeg"

    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename
    )


@router.post("/books/{book_id}/download-audio")
async def download_book_audio(book_id: str, request: BookDownloadRequest, user_id: str = Depends(get_current_user)):
    owner_id = get_book_owner(book_id, user_id)

    book_path = BookService.get_book_path(owner_id, book_id)
    if not os.path.exists(book_path):
        raise HTTPException(status_code=404, detail="Book not found")

    # Get book title from DB
    with get_db() as db:
        book_row = db.query(Book).filter(Book.id == book_id).first()
    book_title = book_row.title if book_row else "book"

    audio_dir = settings.get_audio_dir(user_id, book_id)
    os.makedirs(audio_dir, exist_ok=True)

    # Check for resumable task
    existing_tasks = task_manager.get_all_tasks(user_id)
    resumable_task = None
    for task in existing_tasks:
        if (task.get("type") == "book_audio" and
            task.get("params", {}).get("book_id") == book_id and
            task.get("status") == "failed" and
            task.get("params", {}).get("output_filepath") and
            task.get("params", {}).get("processed_chapters", 0) > 0):
            partial_file = task.get("params", {}).get("output_filepath")
            if os.path.exists(partial_file):
                resumable_task = task
                break

    if resumable_task:
        task_id = resumable_task["id"]
        resume_from = resumable_task["params"].get("processed_chapters", 0)
        output_filepath = resumable_task["params"]["output_filepath"]
        output_filename = os.path.basename(output_filepath)

        task_manager.update_task(
            task_id,
            status=TaskStatus.PENDING,
            progress=0,
            progressText="准备恢复下载...",
            error=None
        )
        is_resume = True
    else:
        timestamp = int(time_module.time())
        safe_filename = "".join(c for c in book_title if c.isalnum() or c in "._- ").strip()
        if not safe_filename:
            safe_filename = "book"
        output_filename = f"{safe_filename}_{timestamp}.mp3"
        output_filepath = os.path.join(audio_dir, output_filename)
        resume_from = 0

        task_id = task_manager.create_task(
            task_type="book_audio",
            params={
                "book_id": book_id,
                "voice": request.voice,
                "rate": request.rate,
                "pitch": request.pitch,
                "output_filepath": output_filepath,
                "processed_chapters": 0
            },
            title=f"生成《{book_title}》音频",
            user_id=user_id
        )
        is_resume = False

    task = asyncio.create_task(generate_book_audio_task(
        task_id=task_id,
        book_id=book_id,
        owner_id=owner_id,
        user_id=user_id,
        voice=request.voice,
        rate=request.rate,
        pitch=request.pitch,
        output_filepath=output_filepath,
        output_filename=output_filename,
        resume_from=resume_from,
        is_resume=is_resume,
        book_title=book_title,
    ))
    task_manager.register_running_task(task_id, task)

    if is_resume:
        return {
            "taskId": task_id,
            "message": f"恢复下载《{book_title}》，从第 {resume_from + 1} 章继续",
            "bookTitle": book_title,
            "resumed": True,
            "resumeFrom": resume_from
        }
    else:
        return {
            "taskId": task_id,
            "message": f"任务已创建，正在后台生成《{book_title}》的音频",
            "bookTitle": book_title,
            "resumed": False
        }


@router.post("/books/{book_id}/download-audio-zip")
async def download_book_audio_zip(book_id: str, request: BookDownloadZipRequest, user_id: str = Depends(get_current_user)):
    owner_id = get_book_owner(book_id, user_id)

    book_path = BookService.get_book_path(owner_id, book_id)
    if not os.path.exists(book_path):
        raise HTTPException(status_code=404, detail="Book not found")

    # Get book title from DB
    with get_db() as db:
        book_row = db.query(Book).filter(Book.id == book_id).first()
    book_title = book_row.title if book_row else "book"

    audio_dir = settings.get_audio_dir(user_id, book_id)
    os.makedirs(audio_dir, exist_ok=True)

    timestamp = int(time_module.time())
    safe_filename = "".join(c for c in book_title if c.isalnum() or c in "._- ").strip()
    if not safe_filename:
        safe_filename = "book"

    temp_dir = os.path.join(audio_dir, f"temp_{book_id}_{timestamp}")
    output_filename = f"{safe_filename}_{timestamp}.zip"
    output_filepath = os.path.join(audio_dir, output_filename)

    task_id = task_manager.create_task(
        task_type="book_audio_zip",
        params={
            "book_id": book_id,
            "voice": request.voice,
            "rate": request.rate,
            "pitch": request.pitch,
            "output_filepath": output_filepath,
            "temp_dir": temp_dir
        },
        title=f"生成《{book_title}》音频（ZIP）",
        user_id=user_id
    )

    task = asyncio.create_task(generate_book_audio_zip_task(
        task_id=task_id,
        book_id=book_id,
        owner_id=owner_id,
        user_id=user_id,
        voice=request.voice,
        rate=request.rate,
        pitch=request.pitch,
        output_filepath=output_filepath,
        output_filename=output_filename,
        temp_dir=temp_dir,
        audio_dir=audio_dir,
        book_title=book_title,
    ))
    task_manager.register_running_task(task_id, task)

    return {
        "taskId": task_id,
        "message": f"任务已创建，正在后台生成《{book_title}》的音频（ZIP格式）",
        "bookTitle": book_title
    }
