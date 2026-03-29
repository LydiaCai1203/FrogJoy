import edge_tts
import hashlib
import json
import os
import re
from typing import List, Dict, Optional, Any
from datetime import datetime
import asyncio
from collections import OrderedDict
from loguru import logger

from app.config import settings


def _audio_url(user_id: str, book_id: str, filename: str) -> str:
    """Build audio URL — uses /api/files/ for per-book audio, /api/tts/download/ for misc."""
    uid = user_id or "_anon"
    bid = book_id or "_misc"
    if user_id and book_id:
        return f"/api/files/{uid}/{bid}/audio/{filename}"
    return f"/api/tts/download/{uid}/{bid}/{filename}"


class AudioCache:
    """音频缓存管理器 — per-book 索引"""

    @staticmethod
    def _cache_index_path(user_id: str, book_id: str) -> str:
        if user_id and book_id:
            return settings.get_cache_index_path(user_id, book_id)
        return os.path.join(settings.data_dir, "users", user_id or "_anon", book_id or "_misc", "cache_index.json")

    @staticmethod
    def _audio_dir(user_id: str, book_id: str) -> str:
        if user_id and book_id:
            return settings.get_audio_dir(user_id, book_id)
        return os.path.join(settings.data_dir, "users", user_id or "_anon", book_id or "_misc", "audio")

    @staticmethod
    def _load_index(user_id: str, book_id: str) -> Dict:
        cache_index_path = AudioCache._cache_index_path(user_id, book_id)
        if os.path.exists(cache_index_path):
            try:
                with open(cache_index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    @staticmethod
    def _save_index(index: Dict, user_id: str, book_id: str) -> None:
        cache_index_path = AudioCache._cache_index_path(user_id, book_id)
        os.makedirs(os.path.dirname(cache_index_path), exist_ok=True)
        with open(cache_index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    @staticmethod
    def generate_cache_key(text: str, voice: str, rate: float, pitch: float,
                           book_id: str = None, chapter_href: str = None,
                           paragraph_index: int = None,
                           is_translated: bool = False) -> str:
        parts = [text, voice, str(rate), str(pitch)]
        if book_id:
            parts.append(book_id)
        if chapter_href:
            parts.append(chapter_href)
        if paragraph_index is not None:
            parts.append(str(paragraph_index))
        if is_translated:
            parts.append("translated")

        content = "|".join(parts)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

    @staticmethod
    def get_cached_entry(cache_key: str, user_id: str, book_id: str) -> Optional[Dict]:
        index = AudioCache._load_index(user_id, book_id)
        audio_dir = AudioCache._audio_dir(user_id, book_id)
        if cache_key in index:
            entry = index[cache_key]
            filepath = os.path.join(audio_dir, entry['filename'])
            if os.path.exists(filepath):
                entry['last_accessed'] = datetime.now().isoformat()
                index[cache_key] = entry
                AudioCache._save_index(index, user_id, book_id)
                return entry
        return None

    @staticmethod
    def save_to_cache(
        cache_key: str,
        filename: str,
        text: str,
        voice: str,
        rate: float,
        pitch: float,
        word_timestamps: List[Dict] = None,
        user_id: str = None,
        book_id: str = None,
        chapter_href: str = None,
        paragraph_index: int = None
    ) -> None:
        index = AudioCache._load_index(user_id, book_id)
        entry = {
            'filename': filename,
            'text_preview': text[:100] + '...' if len(text) > 100 else text,
            'text_length': len(text),
            'voice': voice,
            'rate': rate,
            'pitch': pitch,
            'word_timestamps': word_timestamps or [],
            'created_at': datetime.now().isoformat(),
            'last_accessed': datetime.now().isoformat()
        }
        if book_id:
            entry['book_id'] = book_id
        if chapter_href:
            entry['chapter_href'] = chapter_href
        if paragraph_index is not None:
            entry['paragraph_index'] = paragraph_index

        index[cache_key] = entry
        AudioCache._save_index(index, user_id, book_id)

    @staticmethod
    def get_chapter_cached_entries(book_id: str, chapter_href: str, user_id: str) -> List[Dict]:
        index = AudioCache._load_index(user_id, book_id)
        audio_dir = AudioCache._audio_dir(user_id, book_id)
        entries = []
        for cache_key, entry in index.items():
            if (entry.get('book_id') == book_id and
                entry.get('chapter_href') == chapter_href and
                entry.get('paragraph_index') is not None):
                filepath = os.path.join(audio_dir, entry['filename'])
                if os.path.exists(filepath):
                    entries.append({
                        'cache_key': cache_key,
                        'paragraph_index': entry['paragraph_index'],
                        'filename': entry['filename'],
                        'filepath': filepath,
                        **entry
                    })
        entries.sort(key=lambda x: x['paragraph_index'])
        return entries

    @staticmethod
    def get_cache_stats(user_id: str, book_id: str) -> Dict:
        index = AudioCache._load_index(user_id, book_id)
        audio_dir = AudioCache._audio_dir(user_id, book_id)
        total_size = 0
        for entry in index.values():
            filepath = os.path.join(audio_dir, entry['filename'])
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)

        return {
            'total_entries': len(index),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'entries': list(index.values())
        }

    @staticmethod
    def clear_cache(user_id: str, book_id: str) -> int:
        index = AudioCache._load_index(user_id, book_id)
        audio_dir = AudioCache._audio_dir(user_id, book_id)
        count = 0
        for entry in index.values():
            filepath = os.path.join(audio_dir, entry['filename'])
            if os.path.exists(filepath):
                os.remove(filepath)
                count += 1
        AudioCache._save_index({}, user_id, book_id)
        return count


class AudioMemoryCache:
    """内存音频缓存管理器 - 维护3个音频的缓存窗口"""

    def __init__(self, max_size: int = 3):
        self.max_size = max_size
        self.cache: OrderedDict = OrderedDict()
        self.lock = asyncio.Lock()

    def _make_key(self, book_id: str, chapter_href: str, paragraph_index: int,
                  voice: str, rate: float, pitch: float,
                  is_translated: bool = False) -> tuple:
        return (book_id, chapter_href, paragraph_index, voice, rate, pitch, is_translated)

    async def get(self, book_id: str, chapter_href: str, paragraph_index: int,
                  voice: str, rate: float, pitch: float,
                  is_translated: bool = False) -> Optional[Dict]:
        async with self.lock:
            key = self._make_key(book_id, chapter_href, paragraph_index, voice, rate, pitch, is_translated)
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            return None

    async def put(self, book_id: str, chapter_href: str, paragraph_index: int,
                  voice: str, rate: float, pitch: float, audio_data: Dict,
                  is_translated: bool = False):
        async with self.lock:
            key = self._make_key(book_id, chapter_href, paragraph_index, voice, rate, pitch, is_translated)

            if key in self.cache:
                self.cache[key] = audio_data
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.max_size:
                    self.cache.popitem(last=False)

                self.cache[key] = audio_data

    async def prefetch_range(self, book_id: str, chapter_href: str,
                            start_index: int, end_index: int,
                            sentences: List[str], voice: str, rate: float, pitch: float,
                            user_id: str = None):
        tasks = []
        for idx in range(start_index, min(end_index, len(sentences))):
            cached = await self.get(book_id, chapter_href, idx, voice, rate, pitch)
            if cached:
                continue

            text = sentences[idx]
            cache_key = AudioCache.generate_cache_key(text, voice, rate, pitch, book_id, chapter_href, idx)
            disk_cached = AudioCache.get_cached_entry(cache_key, user_id, book_id)

            if disk_cached:
                audio_data = {
                    "audioUrl": _audio_url(user_id, book_id, disk_cached['filename']),
                    "cached": True,
                    "wordTimestamps": disk_cached.get('word_timestamps', [])
                }
                await self.put(book_id, chapter_href, idx, voice, rate, pitch, audio_data)
            else:
                tasks.append((idx, text))

        if tasks:
            audio_dir = AudioCache._audio_dir(user_id, book_id)
            os.makedirs(audio_dir, exist_ok=True)

            async def generate_and_cache(idx: int, text: str):
                try:
                    cache_key = AudioCache.generate_cache_key(text, voice, rate, pitch, book_id, chapter_href, idx)
                    filename = f"{cache_key}.mp3"
                    filepath = os.path.join(audio_dir, filename)

                    rate_pct = int((rate - 1.0) * 100)
                    rate_str = f"{rate_pct:+d}%"
                    pitch_hz = int((pitch - 1.0) * 50)
                    pitch_str = f"{pitch_hz:+d}Hz"

                    communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
                    await communicate.save(filepath)

                    AudioCache.save_to_cache(
                        cache_key, filename, text, voice, rate, pitch, [],
                        user_id=user_id, book_id=book_id, chapter_href=chapter_href, paragraph_index=idx
                    )

                    result = {
                        "audioUrl": _audio_url(user_id, book_id, filename),
                        "cached": False,
                        "wordTimestamps": []
                    }
                    await self.put(book_id, chapter_href, idx, voice, rate, pitch, result)
                except Exception as e:
                    logger.info(f"[MemoryCache] Failed to prefetch paragraph {idx}: {e}")

            semaphore = asyncio.Semaphore(3)

            async def limited_generate(idx, text):
                async with semaphore:
                    await generate_and_cache(idx, text)

            await asyncio.gather(*[limited_generate(idx, text) for idx, text in tasks])

    async def clear(self):
        async with self.lock:
            self.cache.clear()

    def get_stats(self) -> Dict:
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "keys": list(self.cache.keys())
        }


# 全局内存缓存实例
memory_cache = AudioMemoryCache(max_size=3)


class TTSService:
    DEFAULT_VOICES = {
        "zh": "zh-CN-XiaoxiaoNeural",
        "en": "en-US-JennyNeural",
        "ja": "ja-JP-NanamiNeural",
        "ko": "ko-KR-SunHiNeural",
    }

    @staticmethod
    def detect_language(text: str) -> str:
        if re.search(r'[\u4e00-\u9fff]', text):
            return "zh"
        if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
            return "ja"
        if re.search(r'[\uac00-\ud7af]', text):
            return "ko"
        return "en"

    @staticmethod
    def get_default_voice(text: str) -> str:
        lang = TTSService.detect_language(text)
        return TTSService.DEFAULT_VOICES.get(lang, "en-US-JennyNeural")

    @staticmethod
    async def get_voices() -> List[Dict[str, str]]:
        voices = await edge_tts.list_voices()
        return [
            {
                "name": v["ShortName"],
                "gender": v["Gender"],
                "lang": v["Locale"]
            }
            for v in voices
        ]

    @staticmethod
    async def generate_audio(
        text: str,
        voice: str,
        rate: float = 1.0,
        pitch: float = 1.0,
        user_id: str = None,
        book_id: str = None,
        chapter_href: str = None,
        paragraph_index: int = None,
        is_translated: bool = False,
    ) -> Dict[str, Any]:
        if user_id and book_id:
            audio_dir = settings.get_audio_dir(user_id, book_id)
        else:
            audio_dir = os.path.join(settings.data_dir, "users", user_id or "_anon", "_misc", "audio")
        os.makedirs(audio_dir, exist_ok=True)

        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        detected_lang = TTSService.detect_language(text)
        voice_lang = voice.split("-")[0].lower() if voice else ""

        if voice_lang != detected_lang:
            suggested_voice = TTSService.get_default_voice(text)
            logger.info(f"[TTS] Language mismatch: text is '{detected_lang}', voice is '{voice_lang}'. Using '{suggested_voice}' instead.")
            voice = suggested_voice

        # 1. 优先检查内存缓存
        if book_id and chapter_href is not None and paragraph_index is not None:
            memory_cached = await memory_cache.get(book_id, chapter_href, paragraph_index, voice, rate, pitch, is_translated)
            if memory_cached:
                logger.info(f"[TTS] Memory cache hit: paragraph {paragraph_index} (translated={is_translated})")
                return memory_cached

        # 2. 检查磁盘缓存
        cache_key = AudioCache.generate_cache_key(text, voice, rate, pitch, book_id, chapter_href, paragraph_index, is_translated)
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

        logger.info(f"[TTS] Generating audio: text='{text[:50]}...', voice={voice}, rate={rate_str}, pitch={pitch_str}")

        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)

        filename = f"{cache_key}.mp3"
        filepath = os.path.join(audio_dir, filename)

        word_timestamps = []
        audio_chunks = []

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
            logger.info(f"[TTS] Stream error: {e}")
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
                logger.info(f"[TTS] Retry also failed: {e2}")
                raise e2

        if audio_chunks:
            with open(filepath, 'wb') as f:
                for chunk in audio_chunks:
                    f.write(chunk)
        else:
            await communicate.save(filepath)

        AudioCache.save_to_cache(
            cache_key, filename, text, voice, rate, pitch, word_timestamps,
            user_id=user_id, book_id=book_id, chapter_href=chapter_href, paragraph_index=paragraph_index
        )

        result = {
            "audioUrl": _audio_url(user_id, book_id, filename),
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

        detected_lang = TTSService.detect_language(text)
        voice_lang = voice.split("-")[0].lower() if voice else ""

        if voice_lang != detected_lang:
            suggested_voice = TTSService.get_default_voice(text)
            logger.info(f"[TTS Download] Language mismatch, using '{suggested_voice}'")
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
        logger.info(f"[TTS Download] Generating: {text_len} chars, voice={voice}")

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
            logger.info(f"[TTS Download] Error: {e}")
            raise e

        file_size = os.path.getsize(filepath)

        if progress_callback:
            progress_callback(100, "完成")

        return {
            "downloadUrl": f"/api/tts/download/{user_id or '_anon'}/{book_id or '_misc'}/{output_filename}",
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
            logger.info(f"[TTS] Concatenate error: {e}")
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
                    logger.info(f"[TTS] Error generating paragraph {idx}: {e}")
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

        success = TTSService.concatenate_audio_files(audio_files, output_path)
        if not success:
            raise ValueError("Failed to concatenate audio files")

        file_size = os.path.getsize(output_path)

        if progress_callback:
            progress_callback(100, "完成")

        return {
            "downloadUrl": f"/api/tts/download/{user_id}/{book_id}/{output_filename}",
            "filename": output_filename,
            "size": file_size,
            "sizeFormatted": f"{file_size / (1024*1024):.2f} MB",
            "totalParagraphs": total_paragraphs,
            "cachedParagraphs": cached_count,
            "generatedParagraphs": generated_count
        }
