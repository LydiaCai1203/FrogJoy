"""
AI configuration routes: model config, user preferences, model list.
"""
import uuid
import httpx
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from shared.schemas.ai import (
    AIConfigBulkIn, AIConfigBulkOut,
    UserAIPrefsIn, UserAIPrefsOut,
    ModelOption,
)
from shared.models import AIProviderConfig, UserPreferences
from shared.database import get_db
from app.services.auth_service import AuthService
from app.services.ai.provider import AIService, AIConfig
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/ai", tags=["ai-config"])


# ----- Helper: load AI config for user -----

def _load_ai_config(user_id: str, purpose: str = "chat") -> Optional[AIProviderConfig]:
    """Load AIProviderConfig for a given purpose."""
    with get_db() as db:
        return db.query(AIProviderConfig).filter(
            AIProviderConfig.user_id == user_id,
            AIProviderConfig.purpose == purpose,
        ).first()


def _build_ai_config(user_id: str, config_type: str = "chat") -> AIConfig:
    """
    Build AI config for a given purpose.
    config_type: 'chat' (Ask AI) or 'translation'
    """
    if config_type == "translation":
        # Try translation-specific config first
        row = _load_ai_config(user_id, purpose="translation")
        if row and row.api_key_encrypted:
            decrypted_key = AuthService.decrypt_api_key(row.api_key_encrypted)
            return AIConfig(
                provider_type=row.provider_type,
                base_url=row.base_url,
                api_key=decrypted_key,
                model=row.model,
            )
        # Fall back to chat config
        row = _load_ai_config(user_id, purpose="chat")
        if not row:
            raise HTTPException(status_code=400, detail="AI model not configured. Please configure in Profile.")
        decrypted_key = AuthService.decrypt_api_key(row.api_key_encrypted)
        return AIConfig(
            provider_type=row.provider_type,
            base_url=row.base_url,
            api_key=decrypted_key,
            model=row.model,
        )
    else:
        # Chat config
        row = _load_ai_config(user_id, purpose="chat")
        if not row:
            raise HTTPException(status_code=400, detail="AI model not configured. Please configure in Profile.")
        decrypted_key = AuthService.decrypt_api_key(row.api_key_encrypted)
        return AIConfig(
            provider_type=row.provider_type,
            base_url=row.base_url,
            api_key=decrypted_key,
            model=row.model,
        )


def _load_ai_prefs(user_id: str) -> Optional[UserPreferences]:
    with get_db() as db:
        return db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()


# ----- Routes -----

@router.get("/config", response_model=AIConfigBulkOut)
async def get_ai_config(user_id: str = Depends(get_current_user)):
    chat_row = _load_ai_config(user_id, purpose="chat")
    trans_row = _load_ai_config(user_id, purpose="translation")

    if not chat_row:
        return AIConfigBulkOut(provider_type="openai-chat", base_url="", model="", has_key=False)

    return AIConfigBulkOut(
        provider_type=chat_row.provider_type,
        base_url=chat_row.base_url,
        model=chat_row.model,
        has_key=bool(chat_row.api_key_encrypted),
        translation_provider_type=trans_row.provider_type if trans_row else None,
        translation_base_url=trans_row.base_url if trans_row else None,
        translation_model=trans_row.model if trans_row else None,
        translation_has_key=bool(trans_row.api_key_encrypted) if trans_row else False,
    )


@router.put("/config", response_model=AIConfigBulkOut)
async def save_ai_config(config_in: AIConfigBulkIn, user_id: str = Depends(get_current_user)):
    try:
        with get_db() as db:
            # --- Upsert chat config ---
            chat_row = db.query(AIProviderConfig).filter(
                AIProviderConfig.user_id == user_id,
                AIProviderConfig.purpose == "chat",
            ).first()

            if chat_row:
                chat_row.provider_type = config_in.provider_type
                chat_row.base_url = config_in.base_url
                chat_row.model = config_in.model
                if config_in.api_key:
                    chat_row.api_key_encrypted = AuthService.encrypt_api_key(config_in.api_key)
            else:
                if not config_in.api_key:
                    raise HTTPException(status_code=400, detail="API key is required for initial setup")
                chat_row = AIProviderConfig(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    purpose="chat",
                    provider_type=config_in.provider_type,
                    base_url=config_in.base_url,
                    api_key_encrypted=AuthService.encrypt_api_key(config_in.api_key),
                    model=config_in.model,
                )
                db.add(chat_row)

            # --- Upsert translation config (if provided) ---
            translation_has_key = False
            if config_in.translation_provider_type is not None and config_in.translation_base_url is not None and config_in.translation_model is not None:
                trans_row = db.query(AIProviderConfig).filter(
                    AIProviderConfig.user_id == user_id,
                    AIProviderConfig.purpose == "translation",
                ).first()

                if trans_row:
                    trans_row.provider_type = config_in.translation_provider_type
                    trans_row.base_url = config_in.translation_base_url
                    trans_row.model = config_in.translation_model
                    if config_in.translation_api_key:
                        trans_row.api_key_encrypted = AuthService.encrypt_api_key(config_in.translation_api_key)
                    translation_has_key = bool(trans_row.api_key_encrypted)
                else:
                    encrypted_trans_key = AuthService.encrypt_api_key(config_in.translation_api_key) if config_in.translation_api_key else None
                    if encrypted_trans_key:
                        trans_row = AIProviderConfig(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            purpose="translation",
                            provider_type=config_in.translation_provider_type,
                            base_url=config_in.translation_base_url,
                            api_key_encrypted=encrypted_trans_key,
                            model=config_in.translation_model,
                        )
                        db.add(trans_row)
                        translation_has_key = True
            else:
                # Check if translation config already exists
                trans_row = db.query(AIProviderConfig).filter(
                    AIProviderConfig.user_id == user_id,
                    AIProviderConfig.purpose == "translation",
                ).first()
                translation_has_key = bool(trans_row.api_key_encrypted) if trans_row else False

            db.commit()

        return AIConfigBulkOut(
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
        row = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
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
        existing = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
        if existing:
            existing.enabled_ask_ai = prefs_in.enabled_ask_ai
            existing.enabled_translation = prefs_in.enabled_translation
            existing.translation_mode = prefs_in.translation_mode
            existing.source_lang = prefs_in.source_lang
            existing.target_lang = prefs_in.target_lang
            existing.translation_prompt = prefs_in.translation_prompt
        else:
            existing = UserPreferences(
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
    # Anthropic has no public model list API -- always use curated list
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
            saved = db.query(AIProviderConfig).filter(
                AIProviderConfig.user_id == user_id,
                AIProviderConfig.purpose == "chat",
            ).first()
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

    # No real list available -- only return user's saved model (if any)
    fallback: list[ModelOption] = []
    with get_db() as db:
        saved = db.query(AIProviderConfig).filter(
            AIProviderConfig.user_id == user_id,
            AIProviderConfig.purpose == "chat",
        ).first()
        if saved and saved.model:
            fallback.append(ModelOption(id=saved.model, name=saved.model))
    return fallback
