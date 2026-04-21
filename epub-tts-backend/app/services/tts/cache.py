import hashlib
import json
import os
from typing import List, Dict, Optional
from datetime import datetime

from shared.config import settings


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
