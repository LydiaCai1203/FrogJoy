import edge_tts
import os
from typing import List, Dict, Optional, Any
from loguru import logger

from shared.config import settings
from app.services.tts.cache import AudioCache
from app.services.tts.memory import memory_cache, _tmp_audio_dir, _audio_url, _tmp_audio_url
from app.services.tts.edge import DEFAULT_VOICES, detect_language, get_default_voice, get_voices


class TTSFacade:
    DEFAULT_VOICES = DEFAULT_VOICES

    @staticmethod
    def detect_language(text: str) -> str:
        return detect_language(text)

    @staticmethod
    def get_default_voice(text: str) -> str:
        return get_default_voice(text)

    @staticmethod
    async def get_voices() -> List[Dict[str, str]]:
        return await get_voices()

    @staticmethod
    async def generate_audio(
        text: str,
        voice: str,
        voice_type: str = "edge",
        rate: float = 1.0,
        pitch: float = 1.0,
        user_id: str = None,
        book_id: str = None,
        chapter_href: str = None,
        paragraph_index: int = None,
        is_translated: bool = False,
        persistent: bool = False,
    ) -> Dict[str, Any]:
        if persistent:
            if user_id and book_id:
                audio_dir = settings.get_audio_dir(user_id, book_id)
            else:
                audio_dir = os.path.join(settings.data_dir, "users", user_id or "_anon", "_misc", "audio")
        else:
            audio_dir = _tmp_audio_dir
        os.makedirs(audio_dir, exist_ok=True)

        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        # Only do language-mismatch detection for Edge TTS voices (they have locale prefixes like "zh-CN-...")
        # MiniMax and cloned voices don't follow this naming convention
        if voice_type == "edge":
            detected_lang = detect_language(text)
            voice_lang = voice.split("-")[0].lower() if voice else ""

            if voice_lang != detected_lang:
                suggested_voice = get_default_voice(text)
                logger.debug(f"[TTS] Language mismatch: text is '{detected_lang}', voice is '{voice_lang}'. Using '{suggested_voice}' instead.")
                voice = suggested_voice

        # 1. 优先检查内存缓存
        if book_id and chapter_href is not None and paragraph_index is not None:
            memory_cached = await memory_cache.get(book_id, chapter_href, paragraph_index, voice, rate, pitch, is_translated)
            if memory_cached:
                return memory_cached

        # 2. 检查磁盘缓存（仅持久化模式）
        cache_key = AudioCache.generate_cache_key(text, voice, rate, pitch, book_id, chapter_href, paragraph_index, is_translated)
        if persistent:
            cached_entry = AudioCache.get_cached_entry(cache_key, user_id, book_id)

            if cached_entry:
                result = {
                    "audioUrl": _audio_url(user_id, book_id, cached_entry['filename']),
                    "cached": True,
                    "wordTimestamps": cached_entry.get('word_timestamps', [])
                }
                if book_id and chapter_href is not None and paragraph_index is not None:
                    await memory_cache.put(book_id, chapter_href, paragraph_index, voice, rate, pitch, result, is_translated)
                return result

        # 缓存未命中，生成新音频
        rate_pct = int((rate - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"
        pitch_hz = int((pitch - 1.0) * 50)
        pitch_str = f"{pitch_hz:+d}Hz"

        logger.debug(f"[TTS] Generating audio: text='{text[:50]}...', voice={voice}, voice_type={voice_type}, rate={rate_str}, pitch={pitch_str}")

        filename = f"{cache_key}.mp3"
        filepath = os.path.join(audio_dir, filename)

        word_timestamps = []
        audio_chunks = []

        # Route to appropriate TTS provider
        if voice_type in ("minimax", "cloned") and user_id:
            # Use MiniMax TTS
            try:
                from shared.database import get_db
                from shared.models import TTSProviderConfig
                from app.services.auth_service import AuthService

                with get_db() as db:
                    config = db.query(TTSProviderConfig).filter(
                        TTSProviderConfig.user_id == user_id
                    ).first()

                if not config or not config.api_key_encrypted:
                    raise ValueError("MiniMax TTS 未配置，无法使用克隆音色。请先在设置中配置 MiniMax API Key。")

                api_key = AuthService.decrypt_api_key(config.api_key_encrypted)
                from app.services.voice_clone import VoiceCloneService

                audio_data = await VoiceCloneService.generate_speech_minimax(
                    api_key=api_key,
                    text=text,
                    voice_id=voice,
                    speed=rate,
                    pitch=pitch_hz,
                    emotion="neutral",
                    base_url=config.base_url,
                )

                with open(filepath, 'wb') as f:
                    f.write(audio_data)

                if persistent:
                    AudioCache.save_to_cache(
                        cache_key, filename, text, voice, rate, pitch, word_timestamps,
                        user_id=user_id, book_id=book_id, chapter_href=chapter_href, paragraph_index=paragraph_index
                    )

                audio_url = _audio_url(user_id, book_id, filename) if persistent else _tmp_audio_url(filename)
                result = {
                    "audioUrl": audio_url,
                    "cached": False,
                    "wordTimestamps": word_timestamps
                }

                if book_id and chapter_href is not None and paragraph_index is not None:
                    await memory_cache.put(book_id, chapter_href, paragraph_index, voice, rate, pitch, result, is_translated)

                return result
            except Exception as e:
                logger.error(f"[TTS] MiniMax TTS failed: {e}")
                raise

        # Default: Use Edge TTS
        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)

        try:
            async for chunk in communicate.stream():
                chunk_type = chunk.get("type", "")

                if chunk_type == "audio":
                    audio_chunks.append(chunk.get("data", b""))
                elif chunk_type == "WordBoundary":
                    offset = chunk.get("offset", 0)
                    duration = chunk.get("duration", 0)
                    word_text = chunk.get("text", "")

                    offset_ms = offset // 10000 if offset else 0
                    duration_ms = duration // 10000 if duration else 0

                    if word_text:
                        word_timestamps.append({
                            "text": word_text,
                            "offset": offset_ms,
                            "duration": duration_ms
                        })
        except Exception as e:
            logger.warning(f"[TTS] Stream error: {e}")
            try:
                communicate_retry = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
                await communicate_retry.save(filepath)
                AudioCache.save_to_cache(
                    cache_key, filename, text, voice, rate, pitch, [],
                    user_id=user_id, book_id=book_id, chapter_href=chapter_href, paragraph_index=paragraph_index
                )
                return {
                    "audioUrl": _audio_url(user_id, book_id, filename),
                    "cached": False,
                    "wordTimestamps": []
                }
            except Exception as e2:
                logger.error(f"[TTS] Retry also failed: {e2}")
                raise e2

        if audio_chunks:
            with open(filepath, 'wb') as f:
                for chunk in audio_chunks:
                    f.write(chunk)
        else:
            await communicate.save(filepath)

        if persistent:
            AudioCache.save_to_cache(
                cache_key, filename, text, voice, rate, pitch, word_timestamps,
                user_id=user_id, book_id=book_id, chapter_href=chapter_href, paragraph_index=paragraph_index
            )

        audio_url = _audio_url(user_id, book_id, filename) if persistent else _tmp_audio_url(filename)
        result = {
            "audioUrl": audio_url,
            "cached": False,
            "wordTimestamps": word_timestamps
        }

        if book_id and chapter_href is not None and paragraph_index is not None:
            await memory_cache.put(book_id, chapter_href, paragraph_index, voice, rate, pitch, result, is_translated)

        return result

    @staticmethod
    async def generate_chapter_audio(
        text: str,
        voice: str,
        rate: float = 1.0,
        pitch: float = 1.0,
        filename: str = "chapter",
        user_id: str = None,
        book_id: str = None,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        import time

        if user_id and book_id:
            audio_dir = settings.get_audio_dir(user_id, book_id)
        else:
            audio_dir = os.path.join(settings.data_dir, "users", user_id or "_anon", "_misc", "audio")
        os.makedirs(audio_dir, exist_ok=True)

        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        detected_lang = detect_language(text)
        voice_lang = voice.split("-")[0].lower() if voice else ""

        if voice_lang != detected_lang:
            suggested_voice = get_default_voice(text)
            logger.debug(f"[TTS Download] Language mismatch, using '{suggested_voice}'")
            voice = suggested_voice

        rate_pct = int((rate - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"
        pitch_hz = int((pitch - 1.0) * 50)
        pitch_str = f"{pitch_hz:+d}Hz"

        timestamp = int(time.time())
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
        if not safe_filename:
            safe_filename = "chapter"
        output_filename = f"{safe_filename}_{timestamp}.mp3"
        filepath = os.path.join(audio_dir, output_filename)

        text_len = len(text)
        logger.debug(f"[TTS Download] Generating: {text_len} chars, voice={voice}")

        if progress_callback:
            progress_callback(45, f"开始生成音频 ({text_len} 字符)...")

        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)

        try:
            audio_chunks = []
            chunk_count = 0
            last_progress_update = time.time()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                    chunk_count += 1

                    now = time.time()
                    if progress_callback and (now - last_progress_update) >= 1.0:
                        estimated_total_chunks = text_len / 10
                        progress = min(95, 45 + int((chunk_count / max(estimated_total_chunks, 1)) * 50))
                        progress_callback(progress, f"生成音频中... ({chunk_count} 块)")
                        last_progress_update = now

            if progress_callback:
                progress_callback(96, "写入文件...")

            with open(filepath, 'wb') as f:
                for chunk in audio_chunks:
                    f.write(chunk)

        except Exception as e:
            logger.error(f"[TTS Download] Error: {e}")
            raise e

        file_size = os.path.getsize(filepath)

        if progress_callback:
            progress_callback(100, "完成")

        return {
            "downloadUrl": f"/api/files/audio/{book_id or '_misc'}/{output_filename}",
            "filename": output_filename,
            "size": file_size,
            "sizeFormatted": f"{file_size / (1024*1024):.2f} MB"
        }

    @staticmethod
    def concatenate_audio_files(audio_files: List[str], output_path: str) -> bool:
        try:
            with open(output_path, 'wb') as outfile:
                for audio_file in audio_files:
                    if os.path.exists(audio_file):
                        with open(audio_file, 'rb') as infile:
                            outfile.write(infile.read())
            return True
        except Exception as e:
            logger.error(f"[TTS] Concatenate error: {e}")
            return False

    @staticmethod
    async def generate_chapter_audio_smart(
        book_id: str,
        chapter_href: str,
        sentences: List[str],
        voice: str,
        rate: float = 1.0,
        pitch: float = 1.0,
        filename: str = "chapter",
        user_id: str = None,
        progress_callback: callable = None
    ) -> Dict[str, Any]:
        import time as time_module

        if not sentences:
            raise ValueError("No sentences provided")

        sentences = [s.strip() for s in sentences if s and s.strip()]
        if not sentences:
            raise ValueError("All sentences are empty")

        audio_dir = settings.get_audio_dir(user_id, book_id)
        os.makedirs(audio_dir, exist_ok=True)

        total_paragraphs = len(sentences)

        if progress_callback:
            progress_callback(5, f"检查缓存... 共 {total_paragraphs} 段")

        cached_entries = AudioCache.get_chapter_cached_entries(book_id, chapter_href, user_id)
        cached_map = {entry['paragraph_index']: entry for entry in cached_entries}

        cached_count = len(cached_map)
        missing_count = total_paragraphs - cached_count

        if progress_callback:
            progress_callback(10, f"已缓存 {cached_count}/{total_paragraphs} 段，需生成 {missing_count} 段")

        rate_pct = int((rate - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"
        pitch_hz = int((pitch - 1.0) * 50)
        pitch_str = f"{pitch_hz:+d}Hz"

        audio_files = []
        generated_count = 0

        for idx, text in enumerate(sentences):
            if idx in cached_map:
                audio_files.append(cached_map[idx]['filepath'])
            else:
                cache_key = AudioCache.generate_cache_key(text, voice, rate, pitch, book_id, chapter_href, idx)
                filename_mp3 = f"{cache_key}.mp3"
                filepath = os.path.join(audio_dir, filename_mp3)

                try:
                    communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
                    await communicate.save(filepath)

                    AudioCache.save_to_cache(
                        cache_key, filename_mp3, text, voice, rate, pitch, [],
                        user_id=user_id, book_id=book_id, chapter_href=chapter_href, paragraph_index=idx
                    )

                    audio_files.append(filepath)
                    generated_count += 1

                    if progress_callback:
                        progress = 10 + int((generated_count / max(missing_count, 1)) * 70)
                        progress_callback(progress, f"生成中 {generated_count}/{missing_count} 段")

                except Exception as e:
                    logger.warning(f"[TTS] Error generating paragraph {idx}: {e}")
                    continue

        if not audio_files:
            raise ValueError("No audio generated")

        if progress_callback:
            progress_callback(85, "拼接音频...")

        timestamp = int(time_module.time())
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
        if not safe_filename:
            safe_filename = "chapter"
        output_filename = f"{safe_filename}_{timestamp}.mp3"
        output_path = os.path.join(audio_dir, output_filename)

        success = TTSFacade.concatenate_audio_files(audio_files, output_path)
        if not success:
            raise ValueError("Failed to concatenate audio files")

        file_size = os.path.getsize(output_path)

        if progress_callback:
            progress_callback(100, "完成")

        return {
            "downloadUrl": f"/api/files/audio/{book_id}/{output_filename}",
            "filename": output_filename,
            "size": file_size,
            "sizeFormatted": f"{file_size / (1024*1024):.2f} MB",
            "totalParagraphs": total_paragraphs,
            "cachedParagraphs": cached_count,
            "generatedParagraphs": generated_count
        }


# Alias for backward compatibility
TTSService = TTSFacade
