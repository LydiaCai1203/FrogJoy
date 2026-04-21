# app/deps.py
"""Shared dependency helpers used across multiple routers."""
from fastapi import HTTPException
from shared.database import get_db
from shared.models import Book, UserPreferences, TTSProviderConfig, AIProviderConfig
from app.services.auth_service import AuthService


def get_book_owner(book_id: str, current_user_id: str) -> str:
    """Look up the owner user_id for a book, with access control."""
    with get_db() as db:
        book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if not book.is_public and book.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return book.user_id


def get_book_title(book_id: str, user_id: str) -> str:
    with get_db() as db:
        book = db.query(Book).filter(Book.id == book_id).first()
    return book.title if book else "未知书籍"


def is_audio_persistent(user_id: str) -> bool:
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        return prefs.audio_persistent if prefs and prefs.audio_persistent else False


def is_minimax_configured(user_id: str) -> bool:
    with get_db() as db:
        config = db.query(TTSProviderConfig).filter(TTSProviderConfig.user_id == user_id).first()
        return config is not None and bool(config.api_key_encrypted)


def get_minimax_credentials(user_id: str) -> tuple:
    """Get MiniMax API key and optional base_url override for user. Raises 400 if not configured."""
    with get_db() as db:
        config = db.query(TTSProviderConfig).filter(TTSProviderConfig.user_id == user_id).first()
    if not config or not config.api_key_encrypted:
        raise HTTPException(status_code=400, detail="MiniMax TTS not configured")
    api_key = AuthService.decrypt_api_key(config.api_key_encrypted)
    return api_key, config.base_url
