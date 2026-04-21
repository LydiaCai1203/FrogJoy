from pydantic import BaseModel
from typing import Optional


# ----- New-style per-purpose schemas (post-migration) -----

class AIProviderConfigIn(BaseModel):
    purpose: str  # "chat" | "translation"
    provider_type: str = "openai-chat"
    base_url: str
    api_key: str = ""  # Empty means keep existing key
    model: str


class AIProviderConfigOut(BaseModel):
    purpose: str
    provider_type: str
    base_url: str
    model: str
    has_key: bool  # True if key is configured


# ----- Backward-compat bulk schemas (match current frontend API contract) -----

class AIConfigBulkIn(BaseModel):
    """Backward-compatible bulk config matching existing frontend API contract."""
    provider_type: str = "openai-chat"
    base_url: str
    api_key: str = ""  # Empty means keep existing key
    model: str
    # Translation-specific config (optional - only used when separate translation config is provided)
    translation_provider_type: Optional[str] = None
    translation_base_url: Optional[str] = None
    translation_api_key: Optional[str] = ""  # Empty means keep existing key
    translation_model: Optional[str] = None


class AIConfigBulkOut(BaseModel):
    """Backward-compatible bulk config out matching existing frontend API contract."""
    provider_type: str
    base_url: str
    model: str
    has_key: bool  # True if key is configured
    # Translation config fields
    translation_provider_type: Optional[str] = None
    translation_base_url: Optional[str] = None
    translation_model: Optional[str] = None
    translation_has_key: bool = False


# ----- AI Preferences -----

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


# ----- Chat -----

class ChatMessageIn(BaseModel):
    role: str  # "system" | "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn]
    book_id: Optional[str] = None
    chapter_href: Optional[str] = None
    chapter_title: Optional[str] = None


# ----- Translation -----

class TranslateChapterRequest(BaseModel):
    book_id: str
    chapter_href: str
    sentences: list[str]
    target_lang: str = "Chinese"


class TranslateBookRequest(BaseModel):
    book_id: str
    mode: str = "whole-book"  # "whole-book"


# ----- Models list -----

class ModelOption(BaseModel):
    id: str
    name: str
