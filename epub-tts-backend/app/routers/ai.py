"""
AI 路由 - 模型配置、用户偏好、多轮对话、翻译
"""
import asyncio
import json
import os
import httpx
import uuid
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.exc import IntegrityError

from app.middleware.auth import get_current_user
from app.models.database import get_db
from app.models.models import AIModelConfig, UserAIPreferences, BookTranslation, Book
from app.services.auth_service import AuthService
from app.services.ai_service import AIService, AIConfig, ChatMessage, OpenAIChatProvider, AnthropicProvider
from app.services.book_service import BookService
from app.services.task_service import task_manager, TaskStatus
from app.config import settings
from app.middleware.rate_limit import check_guest_rate_limit, is_guest_user


router = APIRouter(prefix="/ai", tags=["ai"])


# ----- Pydantic Request/Response Models -----

class AIModelConfigIn(BaseModel):
    provider_type: str = "openai-chat"
    base_url: str
    api_key: str = ""  # Empty means keep existing key
    model: str
    # Translation-specific config (optional - only used when separate translation config is provided)
    translation_provider_type: Optional[str] = None
    translation_base_url: Optional[str] = None
    translation_api_key: Optional[str] = ""  # Empty means keep existing key
    translation_model: Optional[str] = None


class AIModelConfigOut(BaseModel):
    provider_type: str
    base_url: str
    model: str
    has_key: bool  # True if key is configured
    # Translation config fields
    translation_provider_type: Optional[str] = None
    translation_base_url: Optional[str] = None
    translation_model: Optional[str] = None
    translation_has_key: bool = False


class UserAIPrefsIn(BaseModel):
    enabled_ask_ai: bool = False
    enabled_translation: bool = False
    translation_mode: str = "current-page"
    source_lang: str = "Auto"
    target_lang: str = "Chinese"
    translation_prompt: Optional[str] = None


class UserAIPrefsOut(BaseModel):
    enabled_ask_ai: bool
    enabled_translation: bool
    translation_mode: str
    source_lang: str
    target_lang: str
    translation_prompt: Optional[str] = None


class ChatMessageIn(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn]
    book_id: Optional[str] = None
    chapter_href: Optional[str] = None
    chapter_title: Optional[str] = None


class TranslateChapterRequest(BaseModel):
    book_id: str
    chapter_href: str
    sentences: list[str]
    target_lang: str = "Chinese"


class TranslateBookRequest(BaseModel):
    book_id: str
    mode: str = "whole-book"  # "whole-book"


class ModelOption(BaseModel):
    id: str
    name: str


# ----- Helper: load AI config for user -----

def _load_ai_config(user_id: str) -> Optional[AIModelConfig]:
    with get_db() as db:
        return db.query(AIModelConfig).filter(AIModelConfig.user_id == user_id).first()


def _build_ai_config(user_id: str, config_type: str = "chat") -> AIConfig:
    """
    Build AI config for a given purpose.
    config_type: 'chat' (Ask AI) or 'translation'
    """
    row = _load_ai_config(user_id)
    if not row:
        raise HTTPException(status_code=400, detail="AI model not configured. Please configure in Profile.")

    if config_type == "translation":
        # Use translation-specific config if set
        if row.translation_provider_type and row.translation_base_url and row.translation_api_key_encrypted and row.translation_model:
            decrypted_key = AuthService.decrypt_api_key(row.translation_api_key_encrypted)
            return AIConfig(
                provider_type=row.translation_provider_type,
                base_url=row.translation_base_url,
                api_key=decrypted_key,
                model=row.translation_model,
            )
        # Fall back to chat config if translation config is not set
        decrypted_key = AuthService.decrypt_api_key(row.api_key_encrypted)
        return AIConfig(
            provider_type=row.provider_type,
            base_url=row.base_url,
            api_key=decrypted_key,
            model=row.model,
        )
    else:
        # Chat config
        decrypted_key = AuthService.decrypt_api_key(row.api_key_encrypted)
        return AIConfig(
            provider_type=row.provider_type,
            base_url=row.base_url,
            api_key=decrypted_key,
            model=row.model,
        )


def _load_ai_prefs(user_id: str) -> Optional[UserAIPreferences]:
    with get_db() as db:
        return db.query(UserAIPreferences).filter(UserAIPreferences.user_id == user_id).first()


def _get_translation_prompt(user_id: str, target_lang: str) -> str:
    prefs = _load_ai_prefs(user_id)
    if prefs and prefs.translation_prompt:
        return prefs.translation_prompt
    return (
        f"You are a professional translator. Translate the following text to {target_lang}. "
        "Keep the original meaning, tone, and formatting. "
        "Only output the translation, no explanations or commentary."
    )


# ----- Routes -----

@router.get("/config", response_model=AIModelConfigOut)
async def get_ai_config(user_id: str = Depends(get_current_user)):
    row = _load_ai_config(user_id)
    if not row:
        return AIModelConfigOut(provider_type="openai-chat", base_url="", model="", has_key=False)
    return AIModelConfigOut(
        provider_type=row.provider_type,
        base_url=row.base_url,
        model=row.model,
        has_key=True,
        translation_provider_type=row.translation_provider_type,
        translation_base_url=row.translation_base_url,
        translation_model=row.translation_model,
        translation_has_key=bool(row.translation_api_key_encrypted),
    )


@router.put("/config", response_model=AIModelConfigOut)
async def save_ai_config(config_in: AIModelConfigIn, user_id: str = Depends(get_current_user)):
    try:
        with get_db() as db:
            existing = db.query(AIModelConfig).filter(AIModelConfig.user_id == user_id).first()
            if existing:
                existing.provider_type = config_in.provider_type
                existing.base_url = config_in.base_url
                existing.model = config_in.model
                # Only update key if a new one is provided
                if config_in.api_key:
                    existing.api_key_encrypted = AuthService.encrypt_api_key(config_in.api_key)
                # Translation config
                if config_in.translation_provider_type is not None:
                    existing.translation_provider_type = config_in.translation_provider_type
                if config_in.translation_base_url is not None:
                    existing.translation_base_url = config_in.translation_base_url
                if config_in.translation_model is not None:
                    existing.translation_model = config_in.translation_model
                if config_in.translation_api_key:
                    existing.translation_api_key_encrypted = AuthService.encrypt_api_key(config_in.translation_api_key)
            else:
                if not config_in.api_key:
                    raise HTTPException(status_code=400, detail="API key is required for initial setup")
                encrypted_key = AuthService.encrypt_api_key(config_in.api_key)
                existing = AIModelConfig(
                    user_id=user_id,
                    provider_type=config_in.provider_type,
                    base_url=config_in.base_url,
                    api_key_encrypted=encrypted_key,
                    model=config_in.model,
                    translation_provider_type=config_in.translation_provider_type,
                    translation_base_url=config_in.translation_base_url,
                    translation_api_key_encrypted=AuthService.encrypt_api_key(config_in.translation_api_key) if config_in.translation_api_key else None,
                    translation_model=config_in.translation_model,
                )
                db.add(existing)
            db.commit()
            db.refresh(existing)
            translation_has_key = bool(existing.translation_api_key_encrypted)
        return AIModelConfigOut(
            provider_type=config_in.provider_type,
            base_url=config_in.base_url,
            model=config_in.model,
            has_key=True,
            translation_provider_type=config_in.translation_provider_type,
            translation_base_url=config_in.translation_base_url,
            translation_model=config_in.translation_model,
            translation_has_key=translation_has_key,
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")


@router.get("/preferences", response_model=UserAIPrefsOut)
async def get_ai_preferences(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.query(UserAIPreferences).filter(UserAIPreferences.user_id == user_id).first()
    if not row:
        return UserAIPrefsOut(
            enabled_ask_ai=False,
            enabled_translation=False,
            translation_mode="current-page",
            source_lang="Auto",
            target_lang="Chinese",
            translation_prompt=None,
        )
    return UserAIPrefsOut(
        enabled_ask_ai=row.enabled_ask_ai,
        enabled_translation=row.enabled_translation,
        translation_mode=row.translation_mode,
        source_lang=row.source_lang or "Auto",
        target_lang=row.target_lang or "Chinese",
        translation_prompt=row.translation_prompt,
    )


@router.put("/preferences", response_model=UserAIPrefsOut)
async def save_ai_preferences(prefs_in: UserAIPrefsIn, user_id: str = Depends(get_current_user)):
    with get_db() as db:
        existing = db.query(UserAIPreferences).filter(UserAIPreferences.user_id == user_id).first()
        if existing:
            existing.enabled_ask_ai = prefs_in.enabled_ask_ai
            existing.enabled_translation = prefs_in.enabled_translation
            existing.translation_mode = prefs_in.translation_mode
            existing.source_lang = prefs_in.source_lang
            existing.target_lang = prefs_in.target_lang
            existing.translation_prompt = prefs_in.translation_prompt
        else:
            existing = UserAIPreferences(
                user_id=user_id,
                enabled_ask_ai=prefs_in.enabled_ask_ai,
                enabled_translation=prefs_in.enabled_translation,
                translation_mode=prefs_in.translation_mode,
                source_lang=prefs_in.source_lang,
                target_lang=prefs_in.target_lang,
                translation_prompt=prefs_in.translation_prompt,
            )
            db.add(existing)
        db.commit()
    return UserAIPrefsOut(
        enabled_ask_ai=prefs_in.enabled_ask_ai,
        enabled_translation=prefs_in.enabled_translation,
        translation_mode=prefs_in.translation_mode,
        source_lang=prefs_in.source_lang,
        target_lang=prefs_in.target_lang,
        translation_prompt=prefs_in.translation_prompt,
    )


@router.get("/models", response_model=list[ModelOption])
async def list_models(
    provider_type: str = "openai-chat",
    base_url: str = Query(default="", description="API base URL"),
    api_key: str = Query(default="", description="API key"),
    user_id: str = Depends(get_current_user),
):
    """Return available model options for a provider type."""
    # Anthropic has no public model list API — always use curated list
    if provider_type == "anthropic":
        return [
            ModelOption(id="claude-sonnet-4-20250514", name="Claude Sonnet 4"),
            ModelOption(id="claude-3-5-sonnet-latest", name="Claude 3.5 Sonnet"),
            ModelOption(id="claude-3-5-haiku-latest", name="Claude 3.5 Haiku"),
            ModelOption(id="claude-3-opus-latest", name="Claude 3 Opus"),
        ]

    # If no api_key provided, try to fetch from user's saved config
    resolved_key = api_key
    if not resolved_key:
        with get_db() as db:
            saved = db.query(AIModelConfig).filter(AIModelConfig.user_id == user_id).first()
            if saved and saved.api_key_encrypted:
                try:
                    resolved_key = AuthService.decrypt_api_key(saved.api_key_encrypted)
                except Exception:
                    pass

    # For OpenAI-compatible providers (DeepSeek, Kimi etc.), fetch real model list
    if base_url and resolved_key:
        # base_url may or may not include /v1, try {base_url}/models first,
        # then {base_url}/v1/models as fallback
        stripped = base_url.rstrip("/")
        model_urls = [
            f"{stripped}/models",
            f"{stripped}/v1/models",
        ]
        for models_url in model_urls:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                    resp = await client.get(
                        models_url,
                        headers={"Authorization": f"Bearer {resolved_key}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        models = data.get("data", [])
                        result = []
                        for m in models:
                            mid = m.get("id", "")
                            if any(skip in mid for skip in ["embedding", "dall-e", "tts", "whisper", "audio"]):
                                continue
                            name = m.get("name") or m.get("id", "")
                            result.append(ModelOption(id=mid, name=name))
                        if result:
                            return result
            except Exception:
                continue

    # No real list available — only return user's saved model (if any)
    fallback: list[ModelOption] = []
    with get_db() as db:
        saved = db.query(AIModelConfig).filter(AIModelConfig.user_id == user_id).first()
        if saved and saved.model:
            fallback.append(ModelOption(id=saved.model, name=saved.model))
    return fallback


@router.post("/chat")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user)):
    """
    Multi-round chat endpoint using SSE (Server-Sent Events) for streaming.
    """
    check_guest_rate_limit(user_id, "chat")
    ai_config = _build_ai_config(user_id)
    messages = [ChatMessage(role=m.role, content=m.content) for m in request.messages]

    async def stream():
        service = AIService(ai_config)
        try:
            async for chunk in service.chat_stream(messages):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/translate/chapter")
async def translate_chapter(request: TranslateChapterRequest, user_id: str = Depends(get_current_user)):
    """Translate a single chapter as SSE stream, sentence by sentence."""
    check_guest_rate_limit(user_id, "translate")
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
    owner_id = _get_book_owner(request.book_id, user_id)
    book_title = _get_book_title(request.book_id, user_id)

    task_id = task_manager.create_task(
        task_type="book_translation",
        params={"book_id": request.book_id, "mode": request.mode},
        title=f"翻译《{book_title}》",
        user_id=user_id,
    )

    asyncio.create_task(_run_book_translation(
        task_id=task_id,
        book_id=request.book_id,
        owner_id=owner_id,
        user_id=user_id,
        mode=request.mode,
    ))

    return {"task_id": task_id, "message": f"开始翻译《{book_title}》"}


async def _run_book_translation(
    task_id: str,
    book_id: str,
    owner_id: str,
    user_id: str,
    mode: str,
):
    """Background task: translate all chapters of a book."""
    try:
        task_manager.start_task(task_id)
        ai_config = _build_ai_config(user_id, config_type="translation")
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

        custom_prompt = _get_translation_prompt(user_id, "Chinese")

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


# ----- Helpers -----

def _get_book_owner(book_id: str, current_user_id: str) -> str:
    with get_db() as db:
        book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if not book.is_public and book.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return book.user_id


def _get_book_title(book_id: str, user_id: str) -> str:
    with get_db() as db:
        book = db.query(Book).filter(Book.id == book_id).first()
    return book.title if book else "未知书籍"
