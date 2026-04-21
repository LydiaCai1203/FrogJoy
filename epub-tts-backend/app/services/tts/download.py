"""
Background task functions for book audio generation.
Extracted from app/api.py's download_book_audio and download_book_audio_zip endpoints.
"""
import asyncio
import os
import shutil
import zipfile
from loguru import logger

import edge_tts

from app.services.book_service import BookService
from app.services.tts.facade import TTSFacade as TTSService
from app.services.task_service import task_manager


async def generate_book_audio_task(
    task_id: str,
    book_id: str,
    owner_id: str,
    user_id: str,
    voice: str,
    rate: float,
    pitch: float,
    output_filepath: str,
    output_filename: str,
    resume_from: int = 0,
    is_resume: bool = False,
    book_title: str = "book",
):
    """Background task: generate full-book audio as a single MP3 file."""
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

        rate_pct = int((rate - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"
        pitch_hz = int((pitch - 1.0) * 50)
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
                    voice_lang = voice.split("-")[0].lower() if voice else ""
                    effective_voice = voice
                    if voice_lang != detected_lang:
                        effective_voice = TTSService.get_default_voice(full_chapter_text)

                    communicate = edge_tts.Communicate(full_chapter_text, effective_voice, rate=rate_str, pitch=pitch_str)

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
                        "voice": voice,
                        "rate": rate,
                        "pitch": pitch,
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
            "downloadUrl": f"/api/files/audio/{book_id}/{output_filename}",
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


async def generate_book_audio_zip_task(
    task_id: str,
    book_id: str,
    owner_id: str,
    user_id: str,
    voice: str,
    rate: float,
    pitch: float,
    output_filepath: str,
    output_filename: str,
    temp_dir: str,
    audio_dir: str,
    book_title: str = "book",
):
    """Background task: generate full-book audio as a ZIP of per-chapter MP3 files."""
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
                    voice=voice,
                    rate=rate,
                    pitch=pitch,
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
                logger.warning(f"[Task] Skip chapter {chapter_info['href']}: {e}")

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
            "downloadUrl": f"/api/files/audio/{book_id}/{output_filename}",
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
