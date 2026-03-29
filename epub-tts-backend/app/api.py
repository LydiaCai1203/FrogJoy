from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
from loguru import logger
from app.services.book_service import BookService
from app.services.tts_service import TTSService, AudioCache
from app.services.task_service import task_manager, TaskStatus
from app.middleware.auth import get_current_user, get_optional_user
from app.models.database import get_db
from app.models.models import Book
from app.config import settings
import asyncio
import os
import edge_tts
import zipfile
import shutil

router = APIRouter()


def _get_book_owner(book_id: str, current_user_id: str) -> str:
    """Look up the owner user_id for a book, with access control."""
    with get_db() as db:
        book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if not book.is_public and book.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return book.user_id


# --- Data Models ---
class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en-US-ChristopherNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    volume: Optional[float] = 1.0
    book_id: Optional[str] = None
    chapter_href: Optional[str] = None
    paragraph_index: Optional[int] = None
    is_translated: Optional[bool] = False

class DownloadRequest(BaseModel):
    sentences: List[str]
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    filename: Optional[str] = "chapter"

class ChapterDownloadRequest(BaseModel):
    book_id: str
    chapter_href: str
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    filename: Optional[str] = "chapter"

class BookDownloadRequest(BaseModel):
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0

class BookDownloadZipRequest(BaseModel):
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0


# --- TTS Routes ---
@router.post("/tts/speak")
async def speak(request: TTSRequest, user_id: str = Depends(get_current_user)):
    logger.info(f"[API] TTS request: text='{request.text[:100] if request.text else 'EMPTY'}...', voice={request.voice}")

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        result = await TTSService.generate_audio(
            text=request.text,
            voice=request.voice,
            rate=request.rate,
            pitch=request.pitch,
            user_id=user_id,
            book_id=request.book_id,
            chapter_href=request.chapter_href,
            paragraph_index=request.paragraph_index,
            is_translated=request.is_translated or False,
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tts/voices")
async def get_voices(lang: str = None):
    voices = await TTSService.get_voices()
    if lang:
        voices = [v for v in voices if v["lang"].lower().startswith(lang.lower())]
    return voices

class PrefetchRequest(BaseModel):
    book_id: str
    chapter_href: str
    sentences: List[str]
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    start_index: int
    end_index: int

@router.post("/tts/prefetch")
async def prefetch_audio(request: PrefetchRequest, user_id: str = Depends(get_current_user)):
    try:
        from app.services.tts_service import memory_cache

        await memory_cache.prefetch_range(
            book_id=request.book_id,
            chapter_href=request.chapter_href,
            start_index=request.start_index,
            end_index=request.end_index,
            sentences=request.sentences,
            voice=request.voice,
            rate=request.rate,
            pitch=request.pitch,
            user_id=user_id
        )

        return {
            "success": True,
            "prefetched": request.end_index - request.start_index,
            "cache_stats": memory_cache.get_stats()
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tts/voices/chinese")
async def get_chinese_voices():
    voices = await TTSService.get_voices()
    chinese_voices = [v for v in voices if v["lang"].startswith("zh")]

    display_names = {
        "zh-CN-XiaoxiaoNeural": "晓晓（活泼女声）⭐",
        "zh-CN-XiaoyiNeural": "晓伊（温柔女声）",
        "zh-CN-YunjianNeural": "云健（成熟男声）",
        "zh-CN-YunxiNeural": "云希（年轻男声）⭐",
        "zh-CN-YunxiaNeural": "云夏（少年音）",
        "zh-CN-YunyangNeural": "云扬（新闻播报）",
        "zh-CN-liaoning-XiaobeiNeural": "晓北（东北话）",
        "zh-CN-shaanxi-XiaoniNeural": "晓妮（陕西话）",
        "zh-HK-HiuGaaiNeural": "曉佳（粤语女声）",
        "zh-HK-HiuMaanNeural": "曉曼（粤语女声）",
        "zh-HK-WanLungNeural": "雲龍（粤语男声）",
        "zh-TW-HsiaoChenNeural": "曉臻（台湾女声）",
        "zh-TW-HsiaoYuNeural": "曉雨（台湾女声）",
        "zh-TW-YunJheNeural": "雲哲（台湾男声）",
    }

    def sort_key(v):
        name = v["name"]
        if "zh-CN-liaoning" in name or "zh-CN-shaanxi" in name:
            return (1, name)
        elif name.startswith("zh-CN"):
            return (0, name)
        elif name.startswith("zh-HK"):
            return (2, name)
        else:
            return (3, name)

    chinese_voices.sort(key=sort_key)

    result = []
    for v in chinese_voices:
        result.append({
            "name": v["name"],
            "displayName": display_names.get(v["name"], v["name"]),
            "gender": v["gender"],
            "lang": v["lang"]
        })

    return result

# --- 缓存管理 Routes ---
@router.get("/tts/cache/stats")
async def get_cache_stats(book_id: str, user_id: str = Depends(get_current_user)):
    return AudioCache.get_cache_stats(user_id, book_id)

@router.get("/tts/cache/chapter")
async def get_chapter_cache(book_id: str, chapter_href: str, user_id: str = Depends(get_current_user)):
    entries = AudioCache.get_chapter_cached_entries(book_id, chapter_href, user_id)
    return {
        "book_id": book_id,
        "chapter_href": chapter_href,
        "entries": entries,
        "cached_count": len(entries)
    }

@router.delete("/tts/cache")
async def clear_cache(book_id: str, user_id: str = Depends(get_current_user)):
    count = AudioCache.clear_cache(user_id, book_id)
    return {"message": f"已清除 {count} 个缓存文件", "cleared_count": count}

# --- 下载音频 Routes ---
@router.post("/tts/download")
async def download_chapter_audio(request: DownloadRequest, user_id: str = Depends(get_current_user)):
    if not request.sentences or len(request.sentences) == 0:
        raise HTTPException(status_code=400, detail="No sentences provided")

    sentences = [s.strip() for s in request.sentences if s and s.strip()]
    if not sentences:
        raise HTTPException(status_code=400, detail="All sentences are empty")

    logger.info(f"[API] Download request: {len(sentences)} sentences, voice={request.voice}")

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

@router.post("/tts/download/chapter")
async def download_chapter_audio_smart(request: ChapterDownloadRequest, user_id: str = Depends(get_current_user)):
    owner_id = _get_book_owner(request.book_id, user_id)

    try:
        chapter = BookService.get_chapter_content(request.book_id, request.chapter_href, owner_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Chapter not found: {e}")

    sentences = chapter.get("sentences", [])
    if not sentences:
        raise HTTPException(status_code=400, detail="Chapter has no content")

    logger.info(f"[API] Smart download: book={request.book_id}, chapter={request.chapter_href}, {len(sentences)} paragraphs")

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

@router.get("/tts/download/{user_id}/{book_id}/{filename}")
async def get_download_file(user_id: str, book_id: str, filename: str):
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
    import time as time_module

    owner_id = _get_book_owner(book_id, user_id)

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

    async def generate_book_audio_task():
        nonlocal output_filepath, resume_from, is_resume, output_filename

        try:
            task_manager.start_task(task_id)

            if is_resume:
                task_manager.update_progress(task_id, 2, f"恢复下载，跳过前 {resume_from} 章...")
            else:
                task_manager.update_progress(task_id, 2, "正在读取书籍目录...")

            toc = BookService.get_toc(book_id, owner_id)
            if not toc:
                raise Exception("Book has no chapters")

            chapters_to_process = []

            def collect_chapters(items):
                for item in items:
                    chapters_to_process.append({
                        "href": item.get("href", ""),
                        "label": item.get("label", "")
                    })
                    if item.get("subitems"):
                        collect_chapters(item["subitems"])

            collect_chapters(toc)
            total_chapters = len(chapters_to_process)

            if total_chapters == 0:
                raise Exception("No chapters found")

            if is_resume:
                task_manager.update_progress(task_id, 5, f"共 {total_chapters} 章，从第 {resume_from + 1} 章继续...")
            else:
                task_manager.update_progress(task_id, 5, f"共 {total_chapters} 章节，开始逐章生成音频...")

            rate_pct = int((request.rate - 1.0) * 100)
            rate_str = f"{rate_pct:+d}%"
            pitch_hz = int((request.pitch - 1.0) * 50)
            pitch_str = f"{pitch_hz:+d}Hz"

            processed = resume_from
            has_audio = is_resume
            file_mode = 'ab' if is_resume else 'wb'

            with open(output_filepath, file_mode) as audio_file:
                for idx, chapter_info in enumerate(chapters_to_process):
                    if idx < resume_from:
                        continue
                    try:
                        chapter = BookService.get_chapter_content(book_id, chapter_info["href"], owner_id)
                        raw_text = chapter.get("text", "").strip()

                        if not raw_text:
                            processed += 1
                            continue

                        chapter_title = chapter_info["label"]
                        if chapter_title:
                            full_chapter_text = f"{chapter_title}。\n{raw_text}"
                        else:
                            full_chapter_text = raw_text

                        detected_lang = TTSService.detect_language(full_chapter_text)
                        voice_lang = request.voice.split("-")[0].lower() if request.voice else ""
                        voice = request.voice
                        if voice_lang != detected_lang:
                            voice = TTSService.get_default_voice(full_chapter_text)

                        communicate = edge_tts.Communicate(full_chapter_text, voice, rate=rate_str, pitch=pitch_str)

                        async for chunk in communicate.stream():
                            if chunk["type"] == "audio":
                                audio_file.write(chunk["data"])
                                has_audio = True

                        audio_file.flush()

                    except Exception as e:
                        logger.warning(f"[Task] Skip chapter {chapter_info['href']}: {e}")

                    processed += 1
                    progress = 5 + int((processed / total_chapters) * 90)
                    task_manager.update_progress(
                        task_id, progress,
                        f"已完成 {processed}/{total_chapters} 章节"
                    )

                    task_manager.update_task(
                        task_id,
                        params={
                            "book_id": book_id,
                            "voice": request.voice,
                            "rate": request.rate,
                            "pitch": request.pitch,
                            "output_filepath": output_filepath,
                            "processed_chapters": processed
                        }
                    )

            if not has_audio:
                if os.path.exists(output_filepath):
                    os.remove(output_filepath)
                raise Exception("No audio generated")

            file_size = os.path.getsize(output_filepath)

            task_manager.complete_task(task_id, {
                "downloadUrl": f"/api/tts/download/{user_id}/{book_id}/{output_filename}",
                "filename": output_filename,
                "size": file_size,
                "bookTitle": book_title,
                "totalChapters": total_chapters
            })

        except asyncio.CancelledError:
            task_manager.fail_task(task_id, "任务已取消")
        except Exception as e:
            import traceback
            traceback.print_exc()
            task_manager.fail_task(task_id, str(e))
        finally:
            task_manager.unregister_running_task(task_id)

    task = asyncio.create_task(generate_book_audio_task())
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
    import time as time_module

    owner_id = _get_book_owner(book_id, user_id)

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

    async def generate_book_audio_zip_task():
        try:
            task_manager.start_task(task_id)
            task_manager.update_progress(task_id, 2, "正在读取书籍目录...")

            toc = BookService.get_toc(book_id, owner_id)
            if not toc:
                raise Exception("Book has no chapters")

            chapters_to_process = []

            def collect_chapters(items, prefix=""):
                for i, item in enumerate(items):
                    chapters_to_process.append({
                        "href": item.get("href", ""),
                        "label": item.get("label", ""),
                        "index": len(chapters_to_process)
                    })
                    if item.get("subitems"):
                        collect_chapters(item["subitems"], f"{prefix}{i+1}.")

            collect_chapters(toc)
            total_chapters = len(chapters_to_process)

            if total_chapters == 0:
                raise Exception("No chapters found")

            task_manager.update_progress(task_id, 5, f"共 {total_chapters} 章节，开始生成...")

            os.makedirs(temp_dir, exist_ok=True)

            chapter_files = []
            total_cached = 0
            total_generated = 0
            processed = 0

            for chapter_info in chapters_to_process:
                try:
                    chapter = BookService.get_chapter_content(book_id, chapter_info["href"], owner_id)
                    sentences = chapter.get("sentences", [])

                    if not sentences:
                        processed += 1
                        continue

                    idx = chapter_info["index"]
                    chapter_label = chapter_info["label"]
                    safe_label = "".join(c for c in chapter_label if c.isalnum() or c in "._- ").strip()
                    if not safe_label:
                        safe_label = "chapter"
                    chapter_filename = f"{idx+1:03d}_{safe_label}.mp3"
                    chapter_filepath = os.path.join(temp_dir, chapter_filename)

                    result = await TTSService.generate_chapter_audio_smart(
                        book_id=book_id,
                        chapter_href=chapter_info["href"],
                        sentences=sentences,
                        voice=request.voice,
                        rate=request.rate,
                        pitch=request.pitch,
                        filename=f"temp_{idx}",
                        user_id=user_id
                    )

                    generated_file = os.path.join(audio_dir, result["filename"])
                    if os.path.exists(generated_file):
                        shutil.move(generated_file, chapter_filepath)
                        chapter_files.append(chapter_filepath)
                        total_cached += result.get("cachedParagraphs", 0)
                        total_generated += result.get("generatedParagraphs", 0)

                except Exception as e:
                    logger.info(f"[Task] Skip chapter {chapter_info['href']}: {e}")

                processed += 1
                progress = 5 + int((processed / total_chapters) * 80)
                task_manager.update_progress(
                    task_id, progress,
                    f"已完成 {processed}/{total_chapters} 章节"
                )

            if not chapter_files:
                raise Exception("No audio generated")

            task_manager.update_progress(task_id, 90, "正在打包 ZIP...")

            with zipfile.ZipFile(output_filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for chapter_file in chapter_files:
                    arcname = os.path.basename(chapter_file)
                    zipf.write(chapter_file, arcname)

            shutil.rmtree(temp_dir, ignore_errors=True)

            file_size = os.path.getsize(output_filepath)

            task_manager.complete_task(task_id, {
                "downloadUrl": f"/api/tts/download/{user_id}/{book_id}/{output_filename}",
                "filename": output_filename,
                "size": file_size,
                "sizeFormatted": f"{file_size / (1024*1024):.2f} MB",
                "bookTitle": book_title,
                "totalChapters": len(chapter_files),
                "cachedParagraphs": total_cached,
                "generatedParagraphs": total_generated
            })

        except asyncio.CancelledError:
            shutil.rmtree(temp_dir, ignore_errors=True)
            task_manager.fail_task(task_id, "任务已取消")
        except Exception as e:
            import traceback
            traceback.print_exc()
            shutil.rmtree(temp_dir, ignore_errors=True)
            task_manager.fail_task(task_id, str(e))
        finally:
            task_manager.unregister_running_task(task_id)

    task = asyncio.create_task(generate_book_audio_zip_task())
    task_manager.register_running_task(task_id, task)

    return {
        "taskId": task_id,
        "message": f"任务已创建，正在后台生成《{book_title}》的音频（ZIP格式）",
        "bookTitle": book_title
    }

# --- 任务管理 Routes ---
@router.get("/tasks")
async def list_tasks(user_id: str = Depends(get_current_user)):
    return task_manager.get_all_tasks(user_id)

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    deleted = task_manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "任务已删除", "taskId": task_id}
