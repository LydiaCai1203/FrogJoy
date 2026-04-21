import edge_tts
import os
import tempfile
import asyncio
from typing import List, Dict, Optional
from collections import OrderedDict
from loguru import logger

from shared.config import settings
from app.services.tts.cache import AudioCache


# 临时音频目录（非持久化模式）
_tmp_audio_dir = os.path.join(tempfile.gettempdir(), "bookreader_audio")
os.makedirs(_tmp_audio_dir, exist_ok=True)


def _audio_url(user_id: str, book_id: str, filename: str) -> str:
    """Build audio URL — includes user_id so it matches the no-auth route in files.py."""
    bid = book_id or "_misc"
    return f"/api/files/audio/{user_id}/{bid}/{filename}"


def _tmp_audio_url(filename: str) -> str:
    """Build URL for temporary (non-persistent) audio files."""
    return f"/api/tts/tmp/{filename}"


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
                            user_id: str = None, voice_type: str = "edge",
                            persistent: bool = False):
        tasks = []
        for idx in range(start_index, min(end_index, len(sentences))):
            cached = await self.get(book_id, chapter_href, idx, voice, rate, pitch)
            if cached:
                continue

            text = sentences[idx]
            if persistent:
                cache_key = AudioCache.generate_cache_key(text, voice, rate, pitch, book_id, chapter_href, idx)
                disk_cached = AudioCache.get_cached_entry(cache_key, user_id, book_id)

                if disk_cached:
                    audio_data = {
                        "audioUrl": _audio_url(user_id, book_id, disk_cached['filename']),
                        "cached": True,
                        "wordTimestamps": disk_cached.get('word_timestamps', [])
                    }
                    await self.put(book_id, chapter_href, idx, voice, rate, pitch, audio_data)
                    continue

            tasks.append((idx, text))

        if tasks:
            audio_dir = AudioCache._audio_dir(user_id, book_id) if persistent else _tmp_audio_dir
            os.makedirs(audio_dir, exist_ok=True)

            # Load MiniMax credentials once if needed
            minimax_api_key = None
            minimax_base_url = None
            if voice_type in ("minimax", "cloned") and user_id:
                try:
                    from shared.database import get_db
                    from shared.models import TTSProviderConfig
                    from app.services.auth_service import AuthService

                    with get_db() as db:
                        config = db.query(TTSProviderConfig).filter(
                            TTSProviderConfig.user_id == user_id
                        ).first()
                    if config and config.api_key_encrypted:
                        minimax_api_key = AuthService.decrypt_api_key(config.api_key_encrypted)
                        minimax_base_url = config.base_url
                    else:
                        raise ValueError("MiniMax TTS 未配置，无法使用克隆音色")
                except Exception as e:
                    logger.warning(f"[Prefetch] Failed to load MiniMax config: {e}")
                    raise

            async def generate_and_cache(idx: int, text: str):
                try:
                    cache_key = AudioCache.generate_cache_key(text, voice, rate, pitch, book_id, chapter_href, idx)
                    filename = f"{cache_key}.mp3"
                    filepath = os.path.join(audio_dir, filename)

                    if voice_type in ("minimax", "cloned") and minimax_api_key:
                        from app.services.voice_clone import VoiceCloneService
                        pitch_hz = int((pitch - 1.0) * 50)
                        audio_bytes = await VoiceCloneService.generate_speech_minimax(
                            api_key=minimax_api_key,
                            text=text,
                            voice_id=voice,
                            speed=rate,
                            pitch=pitch_hz,
                            base_url=minimax_base_url,
                        )
                        with open(filepath, 'wb') as f:
                            f.write(audio_bytes)
                    else:
                        rate_pct = int((rate - 1.0) * 100)
                        rate_str = f"{rate_pct:+d}%"
                        pitch_hz = int((pitch - 1.0) * 50)
                        pitch_str = f"{pitch_hz:+d}Hz"
                        communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
                        await communicate.save(filepath)

                    if persistent:
                        AudioCache.save_to_cache(
                            cache_key, filename, text, voice, rate, pitch, [],
                            user_id=user_id, book_id=book_id, chapter_href=chapter_href, paragraph_index=idx
                        )

                    audio_url = _audio_url(user_id, book_id, filename) if persistent else _tmp_audio_url(filename)
                    result = {
                        "audioUrl": audio_url,
                        "cached": False,
                        "wordTimestamps": []
                    }
                    await self.put(book_id, chapter_href, idx, voice, rate, pitch, result)
                except Exception as e:
                    logger.info(f"[MemoryCache] Failed to prefetch paragraph {idx}: {e}")

            # MiniMax WebSocket is sequential; Edge can be parallel
            if voice_type in ("minimax", "cloned"):
                for idx, text in tasks:
                    await generate_and_cache(idx, text)
            else:
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
