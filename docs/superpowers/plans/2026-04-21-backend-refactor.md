# Backend Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure epub-tts-backend and admin-backend to eliminate code duplication, split oversized files by responsibility, and rationalize API paths — with zero functional regression.

**Architecture:** Extract shared/ layer (models, schemas, database, config) used by both backends. Split mega-files (api.py, tts_service.py) into focused modules. Thin routers delegate to service layer. DB schema refactored (merge preference tables, normalize AI configs, fix date type). Frontend API paths updated to match.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0, Pydantic v2, PostgreSQL, Redis, React/TypeScript (frontend updates)

---

## Phase 0: Database Schema Migration

### Task 0: Alembic migration — merge preferences, normalize AI configs, fix date type

**Files:**
- Create: `epub-tts-backend/alembic/versions/016_refactor_preferences_and_ai.py`

This migration MUST run before the code refactor, so the old code still works with the new schema during the transition. We use a two-step approach: migration creates new tables and copies data, then code refactor updates the ORM models.

- [ ] **Step 1: Create migration file**

```python
# alembic/versions/016_refactor_preferences_and_ai.py
"""Refactor: merge preference tables, normalize AI configs, fix date type

Revision ID: 016_refactor_preferences_and_ai
Revises: 015_add_index_tables
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision = "016_refactor_preferences_and_ai"
down_revision = "015_add_index_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === 1. Create user_preferences (merged from 4 tables) ===
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        # Theme (from user_theme_preferences)
        sa.Column("theme", sa.String(), server_default="eye-care"),
        sa.Column("font_size", sa.Integer(), server_default="18"),
        # Voice (from voice_preferences)
        sa.Column("active_voice_type", sa.String(), server_default="edge"),
        sa.Column("active_edge_voice", sa.String(), server_default="zh-CN-XiaoxiaoNeural"),
        sa.Column("active_minimax_voice", sa.String(), nullable=True),
        sa.Column("active_cloned_voice_id", sa.String(), nullable=True),
        sa.Column("speed", sa.Integer(), server_default="100"),
        sa.Column("pitch", sa.Integer(), server_default="0"),
        sa.Column("emotion", sa.String(), server_default="neutral"),
        sa.Column("audio_persistent", sa.Boolean(), server_default="false"),
        # AI (from user_ai_preferences)
        sa.Column("enabled_ask_ai", sa.Boolean(), server_default="false"),
        sa.Column("enabled_translation", sa.Boolean(), server_default="false"),
        sa.Column("translation_mode", sa.String(), server_default="current-page"),
        sa.Column("source_lang", sa.String(), server_default="Auto"),
        sa.Column("target_lang", sa.String(), server_default="Chinese"),
        sa.Column("translation_prompt", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Migrate data: LEFT JOIN all 3 preference tables on user_id
    op.execute("""
        INSERT INTO user_preferences (
            user_id,
            theme, font_size,
            active_voice_type, active_edge_voice, active_minimax_voice,
            active_cloned_voice_id, speed, pitch, emotion, audio_persistent,
            enabled_ask_ai, enabled_translation, translation_mode,
            source_lang, target_lang, translation_prompt
        )
        SELECT
            u.id,
            COALESCE(t.theme, 'eye-care'),
            COALESCE(t.font_size, 18),
            COALESCE(v.active_voice_type, 'edge'),
            COALESCE(v.active_edge_voice, 'zh-CN-XiaoxiaoNeural'),
            v.active_minimax_voice,
            v.active_cloned_voice_id,
            COALESCE(v.speed, 100),
            COALESCE(v.pitch, 0),
            COALESCE(v.emotion, 'neutral'),
            COALESCE(v.audio_persistent, false),
            COALESCE(a.enabled_ask_ai, false),
            COALESCE(a.enabled_translation, false),
            COALESCE(a.translation_mode, 'current-page'),
            COALESCE(a.source_lang, 'Auto'),
            COALESCE(a.target_lang, 'Chinese'),
            a.translation_prompt
        FROM users u
        LEFT JOIN user_theme_preferences t ON t.user_id = u.id
        LEFT JOIN voice_preferences v ON v.user_id = u.id
        LEFT JOIN user_ai_preferences a ON a.user_id = u.id
        WHERE t.user_id IS NOT NULL
           OR v.user_id IS NOT NULL
           OR a.user_id IS NOT NULL
    """)

    # Drop old tables
    op.drop_table("user_feature_setup")
    op.drop_table("user_ai_preferences")
    op.drop_table("voice_preferences")
    op.drop_table("user_theme_preferences")

    # === 2. Fix reading_stats.date type ===
    op.execute("ALTER TABLE reading_stats ALTER COLUMN date TYPE date USING date::date")

    # === 3. Create ai_provider_configs (normalized from ai_model_configs) ===
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("provider_type", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("api_key_encrypted", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "purpose", name="uq_ai_provider_user_purpose"),
        sa.Index("idx_ai_provider_user", "user_id"),
    )

    # Migrate chat configs
    op.execute("""
        INSERT INTO ai_provider_configs (id, user_id, purpose, provider_type, base_url, api_key_encrypted, model)
        SELECT
            gen_random_uuid()::text,
            user_id, 'chat', provider_type, base_url, api_key_encrypted, model
        FROM ai_model_configs
    """)

    # Migrate translation configs (only where all 4 fields are set)
    op.execute("""
        INSERT INTO ai_provider_configs (id, user_id, purpose, provider_type, base_url, api_key_encrypted, model)
        SELECT
            gen_random_uuid()::text,
            user_id, 'translation',
            translation_provider_type, translation_base_url,
            translation_api_key_encrypted, translation_model
        FROM ai_model_configs
        WHERE translation_provider_type IS NOT NULL
          AND translation_base_url IS NOT NULL
          AND translation_api_key_encrypted IS NOT NULL
          AND translation_model IS NOT NULL
    """)

    # Drop old table
    op.drop_table("ai_model_configs")


def downgrade() -> None:
    # === Reverse 3: Recreate ai_model_configs ===
    op.create_table(
        "ai_model_configs",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("provider_type", sa.String(), nullable=False, server_default="openai-chat"),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("api_key_encrypted", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("translation_provider_type", sa.String(), nullable=True),
        sa.Column("translation_base_url", sa.String(), nullable=True),
        sa.Column("translation_api_key_encrypted", sa.String(), nullable=True),
        sa.Column("translation_model", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Migrate chat rows back
    op.execute("""
        INSERT INTO ai_model_configs (user_id, provider_type, base_url, api_key_encrypted, model)
        SELECT user_id, provider_type, base_url, api_key_encrypted, model
        FROM ai_provider_configs WHERE purpose = 'chat'
    """)

    # Merge translation rows back
    op.execute("""
        UPDATE ai_model_configs SET
            translation_provider_type = t.provider_type,
            translation_base_url = t.base_url,
            translation_api_key_encrypted = t.api_key_encrypted,
            translation_model = t.model
        FROM ai_provider_configs t
        WHERE t.user_id = ai_model_configs.user_id AND t.purpose = 'translation'
    """)

    op.drop_table("ai_provider_configs")

    # === Reverse 2: Fix reading_stats.date back to String ===
    op.execute("ALTER TABLE reading_stats ALTER COLUMN date TYPE varchar USING date::varchar")

    # === Reverse 1: Recreate old preference tables ===
    op.create_table(
        "user_theme_preferences",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("theme", sa.String(), server_default="eye-care"),
        sa.Column("font_size", sa.Integer(), server_default="18"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "voice_preferences",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("active_voice_type", sa.String(), server_default="edge"),
        sa.Column("active_edge_voice", sa.String(), server_default="zh-CN-XiaoxiaoNeural"),
        sa.Column("active_minimax_voice", sa.String(), nullable=True),
        sa.Column("active_cloned_voice_id", sa.String(), nullable=True),
        sa.Column("speed", sa.Integer(), server_default="100"),
        sa.Column("pitch", sa.Integer(), server_default="0"),
        sa.Column("emotion", sa.String(), server_default="neutral"),
        sa.Column("audio_persistent", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "user_ai_preferences",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("enabled_ask_ai", sa.Boolean(), server_default="false"),
        sa.Column("enabled_translation", sa.Boolean(), server_default="false"),
        sa.Column("translation_mode", sa.String(), server_default="current-page"),
        sa.Column("source_lang", sa.String(), server_default="Auto"),
        sa.Column("target_lang", sa.String(), server_default="Chinese"),
        sa.Column("translation_prompt", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "user_feature_setup",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("ai_chat_configured", sa.Boolean(), server_default="false"),
        sa.Column("ai_translation_configured", sa.Boolean(), server_default="false"),
        sa.Column("voice_selection_configured", sa.Boolean(), server_default="false"),
        sa.Column("voice_synthesis_configured", sa.Boolean(), server_default="false"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Migrate data back from user_preferences
    op.execute("""
        INSERT INTO user_theme_preferences (user_id, theme, font_size)
        SELECT user_id, theme, font_size FROM user_preferences
    """)
    op.execute("""
        INSERT INTO voice_preferences (user_id, active_voice_type, active_edge_voice,
            active_minimax_voice, active_cloned_voice_id, speed, pitch, emotion, audio_persistent)
        SELECT user_id, active_voice_type, active_edge_voice,
            active_minimax_voice, active_cloned_voice_id, speed, pitch, emotion, audio_persistent
        FROM user_preferences
    """)
    op.execute("""
        INSERT INTO user_ai_preferences (user_id, enabled_ask_ai, enabled_translation,
            translation_mode, source_lang, target_lang, translation_prompt)
        SELECT user_id, enabled_ask_ai, enabled_translation,
            translation_mode, source_lang, target_lang, translation_prompt
        FROM user_preferences
    """)

    op.drop_table("user_preferences")
```

- [ ] **Step 2: Verify migration syntax**

Run: `cd epub-tts-backend && python -c "from alembic.versions import *; print('OK')"` or simply check the file parses:

```bash
cd epub-tts-backend && python -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('m', 'alembic/versions/016_refactor_preferences_and_ai.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('upgrade:', hasattr(mod, 'upgrade'))
print('downgrade:', hasattr(mod, 'downgrade'))
"
```

Expected: `upgrade: True`, `downgrade: True`

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/016_refactor_preferences_and_ai.py
git commit -m "feat: add migration 016 — merge preferences, normalize AI configs, fix date type"
```

---

## Phase 1: Create shared/ Layer

### Task 1: shared/models — Create new ORM models (post-migration schema)

**Files:**
- Create: `epub-tts-backend/shared/__init__.py`
- Create: `epub-tts-backend/shared/models/__init__.py`
- Create: `epub-tts-backend/shared/models/user.py` — User (no UserFeatureSetup)
- Create: `epub-tts-backend/shared/models/book.py` — Book
- Create: `epub-tts-backend/shared/models/highlight.py` — Highlight
- Create: `epub-tts-backend/shared/models/reading.py` — ReadingStat (date=Date), ReadingProgress
- Create: `epub-tts-backend/shared/models/ai.py` — AIProviderConfig (new), BookTranslation
- Create: `epub-tts-backend/shared/models/tts.py` — TTSProviderConfig, ClonedVoice (no VoicePreferences)
- Create: `epub-tts-backend/shared/models/preferences.py` — UserPreferences (merged)
- Create: `epub-tts-backend/shared/models/index.py` — IndexedBook, IndexedParagraph
- Create: `epub-tts-backend/shared/models/system.py` — SystemSetting

- [ ] **Step 1: Create shared package and Base**

```python
# shared/__init__.py
# Shared layer — models, schemas, database, config
```

```python
# shared/models/__init__.py
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Re-export all models for convenient imports
from shared.models.user import User
from shared.models.book import Book
from shared.models.highlight import Highlight
from shared.models.reading import ReadingStat, ReadingProgress
from shared.models.ai import AIProviderConfig, BookTranslation
from shared.models.tts import TTSProviderConfig, ClonedVoice
from shared.models.preferences import UserPreferences
from shared.models.index import IndexedBook, IndexedParagraph
from shared.models.system import SystemSetting

__all__ = [
    "Base",
    "User",
    "Book",
    "Highlight",
    "ReadingStat", "ReadingProgress",
    "AIProviderConfig", "BookTranslation",
    "TTSProviderConfig", "ClonedVoice",
    "UserPreferences",
    "IndexedBook", "IndexedParagraph",
    "SystemSetting",
]
```

- [ ] **Step 2: Create shared/models/user.py**

```python
# shared/models/user.py
from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from shared.models import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False, server_default="false")
    is_admin = Column(Boolean, default=False, server_default="false")
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    last_login_at = Column(DateTime, nullable=True)

    books = relationship("Book", back_populates="user")
    highlights = relationship("Highlight", back_populates="user")
    reading_stats = relationship("ReadingStat", back_populates="user")
    reading_progress = relationship("ReadingProgress", back_populates="user")
    ai_provider_configs = relationship("AIProviderConfig", back_populates="user")
    book_translations = relationship("BookTranslation", back_populates="user")
    tts_provider_config = relationship("TTSProviderConfig", back_populates="user", uselist=False)
    cloned_voices = relationship("ClonedVoice", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreferences", back_populates="user", uselist=False)
```

Note: `UserFeatureSetup` deleted. Old relationships (`ai_model_config`, `ai_preferences`, `theme_preferences`, `voice_preferences`, `user_feature_setup`) replaced by `ai_provider_configs` (1:M) and `preferences` (1:1).

- [ ] **Step 3: Create shared/models/book.py**

```python
# shared/models/book.py
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from shared.models import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String, nullable=False)
    creator = Column(String)
    cover_url = Column(String)
    file_path = Column(String, nullable=False)
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    last_opened_at = Column(DateTime)

    user = relationship("User", back_populates="books")
    highlights = relationship("Highlight", back_populates="book", cascade="all, delete-orphan")
    reading_stats = relationship("ReadingStat", back_populates="book", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="book", cascade="all, delete-orphan")
    book_translations = relationship("BookTranslation", back_populates="book", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_books_user_id", "user_id"),
        Index("idx_books_is_public", "is_public"),
    )
```

- [ ] **Step 4: Create shared/models/highlight.py**

```python
# shared/models/highlight.py
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from shared.models import Base


class Highlight(Base):
    __tablename__ = "highlights"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    chapter_href = Column(String, nullable=False)
    paragraph_index = Column(Integer, nullable=False, default=0)
    end_paragraph_index = Column(Integer, nullable=False, default=0)
    start_offset = Column(Integer, nullable=False, default=0)
    end_offset = Column(Integer, nullable=False, default=0)
    selected_text = Column(Text, nullable=False)
    color = Column(String, nullable=False, default="yellow")
    note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="highlights")
    book = relationship("Book", back_populates="highlights")

    __table_args__ = (
        Index("idx_highlights_book_chapter", "book_id", "chapter_href"),
        Index("idx_highlights_user_book", "user_id", "book_id"),
    )
```

- [ ] **Step 5: Create shared/models/reading.py**

```python
# shared/models/reading.py
from sqlalchemy import (
    Column, String, Integer, Date, DateTime, ForeignKey, Index, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship
from shared.models import Base


class ReadingStat(Base):
    __tablename__ = "reading_stats"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    date = Column(Date, nullable=False)  # Changed from String to Date
    duration_seconds = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="reading_stats")
    book = relationship("Book", back_populates="reading_stats")

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", "date", name="uq_reading_stats_user_book_date"),
        Index("idx_reading_stats_user_date", "user_id", "date"),
        Index("idx_reading_stats_user_book", "user_id", "book_id"),
    )


class ReadingProgress(Base):
    __tablename__ = "reading_progress"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    book_id = Column(String, ForeignKey("books.id"), primary_key=True)
    chapter_href = Column(String, nullable=False)
    paragraph_index = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="reading_progress")
    book = relationship("Book", back_populates="reading_progress")
```

- [ ] **Step 6: Create shared/models/ai.py**

```python
# shared/models/ai.py
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey, Index, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship
from shared.models import Base


class AIProviderConfig(Base):
    """Normalized AI provider config — one row per (user, purpose)."""
    __tablename__ = "ai_provider_configs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    purpose = Column(String, nullable=False)  # "chat" / "translation"
    provider_type = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    api_key_encrypted = Column(String, nullable=False)
    model = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="ai_provider_configs")

    __table_args__ = (
        UniqueConstraint("user_id", "purpose", name="uq_ai_provider_user_purpose"),
        Index("idx_ai_provider_user", "user_id"),
    )


class BookTranslation(Base):
    __tablename__ = "book_translations"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    chapter_href = Column(String, nullable=False)
    original_content = Column(Text)
    translated_content = Column(Text)
    status = Column(String, default="pending")
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="book_translations")
    book = relationship("Book", back_populates="book_translations")

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", "chapter_href",
                         name="uq_translation_user_book_chapter"),
        Index("idx_translation_book", "user_id", "book_id"),
    )
```

- [ ] **Step 7: Create shared/models/tts.py**

```python
# shared/models/tts.py
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from shared.models import Base


class TTSProviderConfig(Base):
    __tablename__ = "tts_provider_configs"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    provider_type = Column(String, nullable=False, default="edge-tts")
    base_url = Column(String, nullable=True)
    api_key_encrypted = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="tts_provider_config")


class ClonedVoice(Base):
    __tablename__ = "cloned_voices"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    voice_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    audio_sample_path = Column(String, nullable=False)
    lang = Column(String, default="zh")
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="cloned_voices")

    __table_args__ = (
        Index("idx_cloned_voices_user", "user_id"),
    )
```

Note: `VoicePreferences` and `UserThemePreferences` are gone — merged into `UserPreferences`.

- [ ] **Step 7b: Create shared/models/preferences.py**

```python
# shared/models/preferences.py
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from shared.models import Base


class UserPreferences(Base):
    """Merged user preferences (theme + voice + AI prefs)."""
    __tablename__ = "user_preferences"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)

    # Theme (was user_theme_preferences)
    theme = Column(String, default="eye-care")
    font_size = Column(Integer, default=18)

    # Voice (was voice_preferences)
    active_voice_type = Column(String, default="edge")
    active_edge_voice = Column(String, default="zh-CN-XiaoxiaoNeural")
    active_minimax_voice = Column(String, nullable=True)
    active_cloned_voice_id = Column(String, nullable=True)
    speed = Column(Integer, default=100)
    pitch = Column(Integer, default=0)
    emotion = Column(String, default="neutral")
    audio_persistent = Column(Boolean, default=False)

    # AI (was user_ai_preferences)
    enabled_ask_ai = Column(Boolean, default=False)
    enabled_translation = Column(Boolean, default=False)
    translation_mode = Column(String, default="current-page")
    source_lang = Column(String, default="Auto")
    target_lang = Column(String, default="Chinese")
    translation_prompt = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="preferences")
```

- [ ] **Step 8: Create shared/models/index.py**

```python
# shared/models/index.py
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from shared.models import Base


class IndexedBook(Base):
    __tablename__ = "indexed_books"

    book_id = Column(String, ForeignKey("books.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    book_fingerprint = Column(String, nullable=False)
    total_chapters = Column(Integer, nullable=False, default=0)
    total_paragraphs = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    index_version = Column(String, nullable=False, default="v0")
    parsed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    book = relationship("Book")

    __table_args__ = (
        Index("idx_indexed_books_user", "user_id"),
        Index("idx_indexed_books_fingerprint", "book_fingerprint"),
    )


class IndexedParagraph(Base):
    __tablename__ = "indexed_paragraphs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    chapter_idx = Column(Integer, nullable=False)
    chapter_title = Column(String, nullable=True)
    chapter_fp = Column(String, nullable=False)
    para_idx_in_chapter = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_iparagraphs_user_book", "user_id", "book_id"),
        Index("idx_iparagraphs_user_book_chapter", "user_id", "book_id", "chapter_idx"),
    )
```

- [ ] **Step 9: Create shared/models/system.py**

```python
# shared/models/system.py
from sqlalchemy import Column, String, DateTime, func
from shared.models import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 10: Commit**

```bash
cd epub-tts-backend
git add shared/
git commit -m "refactor: create shared/models layer with split ORM models"
```

---

### Task 2: shared/ infrastructure — database, config, redis

**Files:**
- Create: `epub-tts-backend/shared/database.py`
- Create: `epub-tts-backend/shared/config.py`
- Create: `epub-tts-backend/shared/redis_client.py`
- Source: `epub-tts-backend/app/models/database.py`, `epub-tts-backend/app/config.py`, `epub-tts-backend/app/redis_client.py`

- [ ] **Step 1: Create shared/database.py**

Copy exact contents from `app/models/database.py` (no logic changes):

```python
# shared/database.py
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db():
    """Provide a database session. Caller is responsible for commit/rollback."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Create shared/config.py**

Copy exact contents from `app/config.py`:

```python
# shared/config.py
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    elevenlabs_api_key: str = ""
    minimax_base_url: str = "https://api.minimaxi.com"
    fernet_key: str = ""
    data_dir: str = "data"
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    app_url: str = "https://deepkb.com.cn"
    guest_email: str = ""
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_user_book_dir(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.data_dir, "users", user_id, book_id)

    def get_book_path(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "book.epub")

    def get_cover_path(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "cover.jpg")

    def get_audio_dir(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "audio")

    def get_cache_index_path(self, user_id: str, book_id: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "cache_index.json")

    def get_translation_dir(self, user_id: str, book_id: str, target_lang: str) -> str:
        return os.path.join(self.get_user_book_dir(user_id, book_id), "translations", target_lang)

    def get_translation_path(self, user_id: str, book_id: str, target_lang: str, chapter_href: str) -> str:
        import hashlib
        chapter_hash = hashlib.md5(chapter_href.encode("utf-8")).hexdigest()
        return os.path.join(self.get_translation_dir(user_id, book_id, target_lang), f"{chapter_hash}.json")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 3: Create shared/redis_client.py**

Copy exact contents from `app/redis_client.py`:

```python
# shared/redis_client.py
import os
import redis

_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_pool = redis.ConnectionPool.from_url(_REDIS_URL)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)
```

- [ ] **Step 4: Commit**

```bash
git add shared/database.py shared/config.py shared/redis_client.py
git commit -m "refactor: add shared database, config, redis infrastructure"
```

---

### Task 3: shared/schemas — Consolidate Pydantic schemas

**Files:**
- Create: `epub-tts-backend/shared/schemas/__init__.py`
- Create: `epub-tts-backend/shared/schemas/auth.py`
- Create: `epub-tts-backend/shared/schemas/tts.py`
- Create: `epub-tts-backend/shared/schemas/tts_config.py`
- Create: `epub-tts-backend/shared/schemas/ai.py`
- Create: `epub-tts-backend/shared/schemas/task.py`
- Source: scattered across `app/models/user.py`, `app/api.py`, `app/routers/tts_config.py`, `app/routers/ai.py`

- [ ] **Step 1: Create shared/schemas/__init__.py**

```python
# shared/schemas/__init__.py
```

- [ ] **Step 2: Create shared/schemas/auth.py**

Move from `app/models/user.py`:

```python
# shared/schemas/auth.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    is_admin: bool = False
    created_at: Optional[datetime] = None


class UserInDB(BaseModel):
    id: str
    email: str
    password_hash: str
    created_at: Optional[datetime] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


class ThemeIn(BaseModel):
    theme: str


class ThemeOut(BaseModel):
    theme: str


class FontSizeIn(BaseModel):
    font_size: int


class FontSizeOut(BaseModel):
    font_size: int


class VerifyRequest(BaseModel):
    token: str


class ResendRequest(BaseModel):
    email: EmailStr
```

- [ ] **Step 3: Create shared/schemas/tts.py**

Move from `app/api.py`:

```python
# shared/schemas/tts.py
from pydantic import BaseModel
from typing import Optional, List


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en-US-ChristopherNeural"
    voice_type: Optional[str] = "edge"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    volume: Optional[float] = 1.0
    book_id: Optional[str] = None
    chapter_href: Optional[str] = None
    paragraph_index: Optional[int] = None
    is_translated: Optional[bool] = False


class PrefetchRequest(BaseModel):
    book_id: str
    chapter_href: str
    sentences: List[str]
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    voice_type: Optional[str] = "edge"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    start_index: int
    end_index: int


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
```

- [ ] **Step 4: Create shared/schemas/tts_config.py**

Move from `app/routers/tts_config.py`:

```python
# shared/schemas/tts_config.py
from pydantic import BaseModel
from typing import Optional


class TTSConfigIn(BaseModel):
    api_key: str
    base_url: Optional[str] = None


class TTSConfigOut(BaseModel):
    has_api_key: bool = False
    base_url: str = ""


class VoicePreferenceIn(BaseModel):
    active_voice_type: Optional[str] = None
    active_edge_voice: Optional[str] = None
    active_minimax_voice: Optional[str] = None
    active_cloned_voice_id: Optional[str] = None
    speed: Optional[int] = None
    pitch: Optional[int] = None
    emotion: Optional[str] = None
    audio_persistent: Optional[bool] = None


class VoicePreferenceOut(BaseModel):
    active_voice_type: str
    active_edge_voice: str
    active_minimax_voice: Optional[str] = None
    active_cloned_voice_id: Optional[str] = None
    speed: int
    pitch: int
    emotion: str
    audio_persistent: bool


class ProviderStatus(BaseModel):
    edge_tts_configured: bool
    minimax_tts_configured: bool
```

- [ ] **Step 5: Create shared/schemas/ai.py**

Redesigned for the new `ai_provider_configs` table (one row per purpose):

```python
# shared/schemas/ai.py
from pydantic import BaseModel
from typing import Optional


class AIProviderConfigIn(BaseModel):
    """Input for a single AI provider config (one purpose)."""
    purpose: str = "chat"  # "chat" / "translation"
    provider_type: str = "openai-chat"
    base_url: str
    api_key: str = ""  # Empty means keep existing key
    model: str


class AIProviderConfigOut(BaseModel):
    purpose: str
    provider_type: str
    base_url: str
    model: str
    has_key: bool


class AIConfigBulkIn(BaseModel):
    """Bulk update: chat + optional translation config in one request (for frontend compat)."""
    provider_type: str = "openai-chat"
    base_url: str
    api_key: str = ""
    model: str
    translation_provider_type: Optional[str] = None
    translation_base_url: Optional[str] = None
    translation_api_key: Optional[str] = ""
    translation_model: Optional[str] = None


class AIConfigBulkOut(BaseModel):
    """Bulk response: matches frontend's current expectations."""
    provider_type: str
    base_url: str
    model: str
    has_key: bool
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
    role: str
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
    mode: str = "whole-book"


class ModelOption(BaseModel):
    id: str
    name: str
```

- [ ] **Step 6: Create shared/schemas/task.py**

```python
# shared/schemas/task.py
# Currently no dedicated schemas — tasks return plain dicts.
# Placeholder for future typed responses.
```

- [ ] **Step 7: Commit**

```bash
git add shared/schemas/
git commit -m "refactor: consolidate Pydantic schemas into shared/schemas"
```

---

### Task 4: Wire up shared/ — Update all app/ imports

**Files:**
- Modify: `epub-tts-backend/app/models/models.py` — replace with re-exports from shared
- Modify: `epub-tts-backend/app/models/database.py` — replace with re-export from shared
- Modify: `epub-tts-backend/app/models/user.py` — replace with re-export from shared
- Modify: `epub-tts-backend/app/config.py` — replace with re-export from shared
- Modify: `epub-tts-backend/app/redis_client.py` — replace with re-export from shared
- Modify: `epub-tts-backend/alembic/env.py` — update Base import

This is the critical step: we make the old paths into thin re-export shims so all existing imports continue to work. This means zero breakage for all router/service files.

- [ ] **Step 1: Replace app/models/models.py with re-exports**

```python
# app/models/models.py
# Compatibility shim — all models now live in shared/models/
from shared.models import (
    Base,
    User,
    Book,
    Highlight,
    ReadingStat, ReadingProgress,
    AIProviderConfig, BookTranslation,
    TTSProviderConfig, ClonedVoice,
    UserPreferences,
    IndexedBook, IndexedParagraph,
    SystemSetting,
)

# Backward-compat aliases for code that hasn't been updated yet
AIModelConfig = AIProviderConfig
VoicePreferences = UserPreferences
UserThemePreferences = UserPreferences
UserAIPreferences = UserPreferences

__all__ = [
    "Base",
    "User",
    "Book",
    "Highlight",
    "ReadingStat", "ReadingProgress",
    "AIProviderConfig", "AIModelConfig", "BookTranslation",
    "TTSProviderConfig", "ClonedVoice",
    "UserPreferences", "VoicePreferences", "UserThemePreferences", "UserAIPreferences",
    "IndexedBook", "IndexedParagraph",
    "SystemSetting",
]
```

Note: The aliases (`AIModelConfig`, `VoicePreferences`, etc.) let existing router/service code work during the transition. They will be removed in Phase 6 cleanup when all imports are updated to use the new names directly.

- [ ] **Step 2: Replace app/models/database.py with re-export**

```python
# app/models/database.py
# Compatibility shim — database now lives in shared/
from shared.database import engine, SessionLocal, get_db

__all__ = ["engine", "SessionLocal", "get_db"]
```

- [ ] **Step 3: Replace app/models/user.py with re-exports from shared schemas**

```python
# app/models/user.py
# Compatibility shim — schemas now live in shared/schemas/
from shared.schemas.auth import (
    UserCreate, UserLogin, UserResponse, UserInDB,
    Token, TokenData,
    ThemeIn, ThemeOut, FontSizeIn, FontSizeOut,
)

__all__ = [
    "UserCreate", "UserLogin", "UserResponse", "UserInDB",
    "Token", "TokenData",
    "ThemeIn", "ThemeOut", "FontSizeIn", "FontSizeOut",
]
```

- [ ] **Step 4: Replace app/config.py with re-export**

```python
# app/config.py
# Compatibility shim — config now lives in shared/
from shared.config import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
```

- [ ] **Step 5: Replace app/redis_client.py with re-export**

```python
# app/redis_client.py
# Compatibility shim — redis now lives in shared/
from shared.redis_client import get_redis

__all__ = ["get_redis"]
```

- [ ] **Step 6: Update alembic/env.py**

Change the Base import:

```python
# In alembic/env.py, replace:
#   from app.models.models import Base
# with:
from shared.models import Base
```

- [ ] **Step 7: Verify app starts without errors**

Run: `cd epub-tts-backend && python -c "from app.main import app; print('OK')"`

Expected: `OK` (no import errors)

- [ ] **Step 8: Commit**

```bash
git add app/models/ app/config.py app/redis_client.py alembic/env.py
git commit -m "refactor: wire shared/ layer with compatibility shims"
```

---

## Phase 2: Restructure Services

### Task 5: Split tts_service.py into tts/ package

**Files:**
- Create: `epub-tts-backend/app/services/tts/__init__.py`
- Create: `epub-tts-backend/app/services/tts/cache.py`
- Create: `epub-tts-backend/app/services/tts/memory.py`
- Create: `epub-tts-backend/app/services/tts/edge.py`
- Create: `epub-tts-backend/app/services/tts/minimax.py`
- Create: `epub-tts-backend/app/services/tts/facade.py`
- Create: `epub-tts-backend/app/services/tts/download.py`
- Source: `epub-tts-backend/app/services/tts_service.py`, `epub-tts-backend/app/services/voice_clone.py`

- [ ] **Step 1: Create tts/cache.py**

Move `AudioCache` class (lines 34-183 of tts_service.py) verbatim. Update imports to use shared/:

```python
# app/services/tts/cache.py
import json
import os
import hashlib
from typing import Dict, List, Optional
from datetime import datetime

from shared.config import settings


class AudioCache:
    """Per-book disk cache index manager."""

    # Copy the entire AudioCache class from tts_service.py lines 34-183 verbatim.
    # Only change: `from app.config import settings` → already using `from shared.config import settings`
    ...
```

The actual code is an exact copy of lines 34-183 from `app/services/tts_service.py`.

- [ ] **Step 2: Create tts/memory.py**

Move `AudioMemoryCache` class (lines 186-342) and the `memory_cache` global instance. Also move the helper functions `_audio_url`, `_tmp_audio_url`, `_tmp_audio_dir`:

```python
# app/services/tts/memory.py
import os
import asyncio
import tempfile
from collections import OrderedDict
from typing import Dict, List, Optional
from loguru import logger

from shared.config import settings
from app.services.tts.cache import AudioCache

# Temporary audio directory
_tmp_audio_dir = os.path.join(tempfile.gettempdir(), "bookreader_audio")
os.makedirs(_tmp_audio_dir, exist_ok=True)


def _audio_url(user_id: str, book_id: str, filename: str) -> str:
    # Copy from tts_service.py lines 20-26 verbatim
    ...


def _tmp_audio_url(filename: str) -> str:
    # Copy from tts_service.py lines 29-31 verbatim
    ...


class AudioMemoryCache:
    # Copy from tts_service.py lines 186-342 verbatim
    # Update internal imports: AudioCache is now from app.services.tts.cache
    ...


# Global instance
memory_cache = AudioMemoryCache(max_size=3)
```

- [ ] **Step 3: Create tts/edge.py**

Extract Edge TTS generation logic from `TTSService`:

```python
# app/services/tts/edge.py
import re
import edge_tts
from typing import List, Dict
from loguru import logger


DEFAULT_VOICES = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
}


def detect_language(text: str) -> str:
    # Copy from TTSService.detect_language verbatim
    ...


def get_default_voice(text: str) -> str:
    # Copy from TTSService.get_default_voice verbatim
    ...


async def get_voices() -> List[Dict[str, str]]:
    # Copy from TTSService.get_voices verbatim
    ...


async def generate_audio_edge(
    text: str, voice: str, rate_str: str, pitch_str: str, filepath: str
) -> List[Dict]:
    """Generate audio using Edge TTS. Returns word_timestamps."""
    # Extract the Edge TTS streaming logic from TTSService.generate_audio lines 511-573
    ...
```

- [ ] **Step 4: Create tts/minimax.py**

Merge `voice_clone.py` content into here. The entire `VoiceCloneService` class plus the MiniMax TTS branch from `TTSService.generate_audio`:

```python
# app/services/tts/minimax.py
# Copy the entire content of app/services/voice_clone.py verbatim.
# This already contains: clone_voice(), generate_speech_minimax(),
# validate_api_key(), get_minimax_voices_sync()
# Only update: `from app.config import settings` → `from shared.config import settings`
```

- [ ] **Step 5: Create tts/facade.py**

This replaces the `TTSService` class. It delegates to edge/minimax and manages caching:

```python
# app/services/tts/facade.py
import os
from typing import Dict, Any, Optional
from loguru import logger

from shared.config import settings
from app.services.tts.cache import AudioCache
from app.services.tts.memory import memory_cache, _audio_url, _tmp_audio_url, _tmp_audio_dir
from app.services.tts import edge as edge_tts_provider


class TTSFacade:
    """Unified TTS entry point. Routes to edge/minimax, manages caching."""

    @staticmethod
    def detect_language(text: str) -> str:
        return edge_tts_provider.detect_language(text)

    @staticmethod
    def get_default_voice(text: str) -> str:
        return edge_tts_provider.get_default_voice(text)

    @staticmethod
    async def get_voices():
        return await edge_tts_provider.get_voices()

    @staticmethod
    async def generate_audio(...) -> Dict[str, Any]:
        # Copy TTSService.generate_audio logic verbatim
        # Internal calls change to:
        #   edge_tts_provider.detect_language() instead of TTSService.detect_language()
        #   edge_tts_provider.generate_audio_edge() for Edge
        #   VoiceCloneService.generate_speech_minimax() for MiniMax
        ...

    @staticmethod
    async def generate_chapter_audio(...) -> Dict[str, Any]:
        # Copy TTSService.generate_chapter_audio verbatim
        ...

    @staticmethod
    def concatenate_audio_files(...) -> bool:
        # Copy TTSService.concatenate_audio_files verbatim
        ...

    @staticmethod
    async def generate_chapter_audio_smart(...) -> Dict[str, Any]:
        # Copy TTSService.generate_chapter_audio_smart verbatim
        ...
```

- [ ] **Step 6: Create tts/download.py**

Move the book download background task logic from `app/api.py`:

```python
# app/services/tts/download.py
import os
import asyncio
import shutil
import zipfile
from loguru import logger

from shared.config import settings
from app.services.book_service import BookService
from app.services.task_service import task_manager, TaskStatus
from app.services.tts.facade import TTSFacade
from app.services.tts import edge as edge_tts_provider
import edge_tts


async def generate_book_audio_task(
    task_id, book_id, owner_id, user_id, book_title,
    voice, rate, pitch, output_filepath, output_filename,
    resume_from=0, is_resume=False,
):
    """Background task: generate full book audio as single MP3."""
    # Copy the generate_book_audio_task() inner function from api.py lines 336-459 verbatim
    ...


async def generate_book_audio_zip_task(
    task_id, book_id, owner_id, user_id, book_title,
    voice, rate, pitch, output_filepath, output_filename, temp_dir,
):
    """Background task: generate full book audio as ZIP of chapter MP3s."""
    # Copy the generate_book_audio_zip_task() inner function from api.py lines 521-636 verbatim
    ...
```

- [ ] **Step 7: Create tts/__init__.py**

```python
# app/services/tts/__init__.py
```

- [ ] **Step 8: Create compatibility shim for old imports**

Replace `app/services/tts_service.py` with re-exports so existing code doesn't break:

```python
# app/services/tts_service.py
# Compatibility shim — TTS service now lives in app/services/tts/
from app.services.tts.cache import AudioCache
from app.services.tts.memory import AudioMemoryCache, memory_cache, _tmp_audio_dir
from app.services.tts.facade import TTSFacade as TTSService

__all__ = ["AudioCache", "AudioMemoryCache", "memory_cache", "TTSService", "_tmp_audio_dir"]
```

Replace `app/services/voice_clone.py` with re-export:

```python
# app/services/voice_clone.py
# Compatibility shim — voice clone now lives in app/services/tts/minimax.py
from app.services.tts.minimax import VoiceCloneService

__all__ = ["VoiceCloneService"]
```

- [ ] **Step 9: Verify imports work**

Run: `cd epub-tts-backend && python -c "from app.services.tts_service import TTSService, AudioCache, memory_cache; from app.services.voice_clone import VoiceCloneService; print('OK')"`

Expected: `OK`

- [ ] **Step 10: Commit**

```bash
git add app/services/tts/ app/services/tts_service.py app/services/voice_clone.py
git commit -m "refactor: split tts_service.py into tts/ package"
```

---

### Task 6: Split AI service

**Files:**
- Create: `epub-tts-backend/app/services/ai/__init__.py`
- Create: `epub-tts-backend/app/services/ai/provider.py`
- Create: `epub-tts-backend/app/services/ai/translation.py`
- Source: `epub-tts-backend/app/services/ai_service.py`, `epub-tts-backend/app/routers/ai.py` (translation task)

- [ ] **Step 1: Create ai/__init__.py**

```python
# app/services/ai/__init__.py
```

- [ ] **Step 2: Create ai/provider.py**

Copy the entire `app/services/ai_service.py` verbatim. Only update config import:

```python
# app/services/ai/provider.py
# Copy entire content of app/services/ai_service.py
# Change: from app.config import settings → from shared.config import settings (if present)
```

- [ ] **Step 3: Create ai/translation.py**

Move `_run_book_translation()` from `app/routers/ai.py` (lines 475-576):

```python
# app/services/ai/translation.py
import asyncio
import uuid
from loguru import logger

from shared.database import get_db
from shared.models import BookTranslation
from app.services.ai.provider import AIService
from app.services.book_service import BookService
from app.services.task_service import task_manager


async def run_book_translation(
    task_id: str, book_id: str, owner_id: str, user_id: str,
    mode: str, ai_config, custom_prompt: str,
):
    """Background task: translate all chapters of a book."""
    # Copy _run_book_translation() from ai.py lines 475-576 verbatim
    # Change: receives ai_config and custom_prompt as params instead of building internally
    ...
```

- [ ] **Step 4: Create compatibility shim**

```python
# app/services/ai_service.py
# Compatibility shim
from app.services.ai.provider import AIService, AIConfig, ChatMessage, OpenAIChatProvider, AnthropicProvider

__all__ = ["AIService", "AIConfig", "ChatMessage", "OpenAIChatProvider", "AnthropicProvider"]
```

- [ ] **Step 5: Verify**

Run: `cd epub-tts-backend && python -c "from app.services.ai_service import AIService, AIConfig; print('OK')"`

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add app/services/ai/ app/services/ai_service.py
git commit -m "refactor: split ai_service into ai/ package with translation service"
```

---

## Phase 3: Restructure Routers

### Task 7: Create app/deps.py with shared dependencies

**Files:**
- Create: `epub-tts-backend/app/deps.py`

- [ ] **Step 1: Create deps.py**

Extract duplicated helper functions from api.py and ai.py:

```python
# app/deps.py
"""Shared route dependencies and helper functions."""
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
    """Check if user has audio persistence enabled."""
    with get_db() as db:
        prefs = db.query(UserPreferences).filter(
            UserPreferences.user_id == user_id
        ).first()
        return prefs.audio_persistent if prefs and prefs.audio_persistent else False


def is_minimax_configured(user_id: str) -> bool:
    """Check if user has a valid MiniMax API key configured."""
    with get_db() as db:
        config = db.query(TTSProviderConfig).filter(
            TTSProviderConfig.user_id == user_id
        ).first()
        return config is not None and bool(config.api_key_encrypted)


def get_minimax_credentials(user_id: str) -> tuple:
    """Get MiniMax API key and optional base_url. Raises 400 if not configured."""
    with get_db() as db:
        config = db.query(TTSProviderConfig).filter(
            TTSProviderConfig.user_id == user_id
        ).first()
    if not config or not config.api_key_encrypted:
        raise HTTPException(status_code=400, detail="MiniMax TTS not configured")
    api_key = AuthService.decrypt_api_key(config.api_key_encrypted)
    return api_key, config.base_url


def is_ai_configured(user_id: str, purpose: str = "chat") -> bool:
    """Check if user has an AI provider configured for given purpose."""
    with get_db() as db:
        config = db.query(AIProviderConfig).filter(
            AIProviderConfig.user_id == user_id,
            AIProviderConfig.purpose == purpose,
        ).first()
        return config is not None
```

- [ ] **Step 2: Commit**

```bash
git add app/deps.py
git commit -m "refactor: create app/deps.py with shared route dependencies"
```

---

### Task 8: Split api.py into tts.py, tts_download.py, tts_cache.py, tasks.py

**Files:**
- Create: `epub-tts-backend/app/routers/tts.py`
- Create: `epub-tts-backend/app/routers/tts_download.py`
- Create: `epub-tts-backend/app/routers/tts_cache.py`
- Create: `epub-tts-backend/app/routers/tasks.py`
- Modify: `epub-tts-backend/app/api.py` → becomes compatibility shim

- [ ] **Step 1: Create routers/tts.py**

Move `/tts/speak`, `/tts/prefetch`, `/tts/tmp/{filename}` from api.py:

```python
# app/routers/tts.py
import os
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import FileResponse
from loguru import logger

from shared.schemas.tts import TTSRequest, PrefetchRequest
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import get_client_ip, check_guest_tts_rate_limit, is_guest_user
from app.deps import is_audio_persistent
from app.services.tts.facade import TTSFacade
from app.services.tts.memory import memory_cache, _tmp_audio_dir

router = APIRouter(prefix="/tts", tags=["tts"])


@router.post("/speak")
async def speak(request: TTSRequest, raw_request: Request, user_id: str = Depends(get_current_user)):
    # Copy from api.py @router.post("/tts/speak") verbatim
    # Replace: TTSService → TTSFacade
    # Replace: _is_audio_persistent(user_id) → is_audio_persistent(user_id)
    ...


@router.post("/prefetch")
async def prefetch_audio(request: PrefetchRequest, user_id: str = Depends(get_current_user)):
    # Copy from api.py @router.post("/tts/prefetch") verbatim
    ...


@router.get("/tmp/{filename}")
async def serve_tmp_audio(filename: str):
    # Copy from api.py @router.get("/tts/tmp/{filename}") verbatim
    ...
```

- [ ] **Step 2: Create routers/tts_download.py**

Move all download routes from api.py:

```python
# app/routers/tts_download.py
import os
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from loguru import logger

from shared.schemas.tts import (
    DownloadRequest, ChapterDownloadRequest,
    BookDownloadRequest, BookDownloadZipRequest,
)
from shared.database import get_db
from shared.models import Book
from shared.config import settings
from app.middleware.auth import get_current_user
from app.deps import get_book_owner
from app.services.book_service import BookService
from app.services.tts.facade import TTSFacade
from app.services.tts.download import generate_book_audio_task, generate_book_audio_zip_task
from app.services.task_service import task_manager, TaskStatus

router = APIRouter(tags=["tts-download"])


@router.post("/tts/download/chapter")
async def download_chapter_audio(request: DownloadRequest, user_id: str = Depends(get_current_user)):
    # Copy from api.py POST /tts/download verbatim
    ...


@router.post("/tts/download/chapter/smart")
async def download_chapter_audio_smart(request: ChapterDownloadRequest, user_id: str = Depends(get_current_user)):
    # Copy from api.py POST /tts/download/chapter verbatim
    ...


@router.post("/books/{book_id}/download-audio")
async def download_book_audio(book_id: str, request: BookDownloadRequest, user_id: str = Depends(get_current_user)):
    # Copy from api.py verbatim, but delegate to tts/download.py for the background task
    ...


@router.post("/books/{book_id}/download-audio-zip")
async def download_book_audio_zip(book_id: str, request: BookDownloadZipRequest, user_id: str = Depends(get_current_user)):
    # Copy from api.py verbatim, but delegate to tts/download.py for the background task
    ...


@router.get("/files/audio/{book_id}/{filename}")
async def get_download_file(book_id: str, filename: str, user_id: str = Depends(get_current_user)):
    """Serve audio file. User_id from auth token, not URL."""
    audio_dir = settings.get_audio_dir(user_id, book_id)
    filepath = os.path.join(audio_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "application/zip" if filename.endswith(".zip") else "audio/mpeg"
    return FileResponse(filepath, media_type=media_type, filename=filename)
```

- [ ] **Step 3: Create routers/tts_cache.py**

```python
# app/routers/tts_cache.py
from fastapi import APIRouter, Depends
from app.middleware.auth import get_current_user
from app.services.tts.cache import AudioCache

router = APIRouter(prefix="/tts/cache", tags=["tts-cache"])


@router.get("/stats")
async def get_cache_stats(book_id: str, user_id: str = Depends(get_current_user)):
    return AudioCache.get_cache_stats(user_id, book_id)


@router.get("/chapter")
async def get_chapter_cache(book_id: str, chapter_href: str, user_id: str = Depends(get_current_user)):
    entries = AudioCache.get_chapter_cached_entries(book_id, chapter_href, user_id)
    return {
        "book_id": book_id,
        "chapter_href": chapter_href,
        "entries": entries,
        "cached_count": len(entries)
    }


@router.delete("")
async def clear_cache(book_id: str, user_id: str = Depends(get_current_user)):
    count = AudioCache.clear_cache(user_id, book_id)
    return {"message": f"已清除 {count} 个缓存文件", "cleared_count": count}
```

- [ ] **Step 4: Create routers/tasks.py**

```python
# app/routers/tasks.py
from fastapi import APIRouter, HTTPException, Depends
from app.middleware.auth import get_current_user
from app.services.task_service import task_manager

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(user_id: str = Depends(get_current_user)):
    return task_manager.get_all_tasks(user_id)


@router.get("/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    deleted = task_manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "任务已删除", "taskId": task_id}
```

- [ ] **Step 5: Commit**

```bash
git add app/routers/tts.py app/routers/tts_download.py app/routers/tts_cache.py app/routers/tasks.py
git commit -m "refactor: split api.py into tts, tts_download, tts_cache, tasks routers"
```

---

### Task 9: Split tts_config.py into tts_config.py + voices.py

**Files:**
- Create: `epub-tts-backend/app/routers/voices.py`
- Modify: `epub-tts-backend/app/routers/tts_config.py`

- [ ] **Step 1: Create routers/voices.py**

Move voice list, clone, preferences routes out of tts_config.py:

```python
# app/routers/voices.py
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from loguru import logger

from shared.schemas.tts_config import VoicePreferenceIn, VoicePreferenceOut
from shared.database import get_db
from shared.models import ClonedVoice, VoicePreferences, UserFeatureSetup
from shared.config import settings
from app.middleware.auth import get_current_user
from app.deps import is_minimax_configured, get_minimax_credentials
from app.services.tts.minimax import VoiceCloneService
from app.services.tts.facade import TTSFacade
from app.services.system_settings import get_system_setting

router = APIRouter(prefix="/voices", tags=["voices"])

# Copy _EDGE_DISPLAY_NAMES dict from tts_config.py

# GET /voices — all voices
# GET /voices/edge
# GET /voices/minimax
# POST /voices/clone
# GET /voices/cloned
# DELETE /voices/cloned/{voice_id}
# GET /voices/preferences
# PUT /voices/preferences

# Each route: copy verbatim from tts_config.py, update imports
```

- [ ] **Step 2: Slim down tts_config.py**

Keep only: GET/PUT/DELETE /tts/config and GET /tts/providers/status. Update imports to use shared/:

```python
# app/routers/tts_config.py
from fastapi import APIRouter, HTTPException, Depends
from shared.schemas.tts_config import TTSConfigIn, TTSConfigOut, ProviderStatus
from shared.database import get_db
from shared.models import TTSProviderConfig, UserFeatureSetup
from shared.config import settings
from app.middleware.auth import get_current_user
from app.services.auth_service import AuthService
from app.services.tts.minimax import VoiceCloneService
from app.deps import is_minimax_configured

router = APIRouter(prefix="/tts", tags=["tts-config"])

# Keep: GET /config, PUT /config, DELETE /config, GET /providers/status
# Copy verbatim, update imports
```

- [ ] **Step 3: Commit**

```bash
git add app/routers/voices.py app/routers/tts_config.py
git commit -m "refactor: extract voices.py from tts_config.py"
```

---

### Task 10: Split ai.py into ai_config.py, ai_chat.py, ai_translate.py

**Files:**
- Create: `epub-tts-backend/app/routers/ai_config.py`
- Create: `epub-tts-backend/app/routers/ai_chat.py`
- Create: `epub-tts-backend/app/routers/ai_translate.py`
- Modify: `epub-tts-backend/app/routers/ai.py` → becomes shim

- [ ] **Step 1: Create routers/ai_config.py**

```python
# app/routers/ai_config.py
# Move: GET/PUT /ai/config, GET/PUT /ai/preferences, GET /ai/models
# Move: helper functions _load_ai_config, _build_ai_config, _load_ai_prefs
# Update imports to shared/
```

- [ ] **Step 2: Create routers/ai_chat.py**

```python
# app/routers/ai_chat.py
# Move: POST /ai/chat
# Update imports to shared/
```

- [ ] **Step 3: Create routers/ai_translate.py**

```python
# app/routers/ai_translate.py
# Move: POST /ai/translate/chapter, POST /ai/translate/book
# Move: GET /ai/translate/{book_id}/chapter, GET /ai/translate/{book_id}
# Move: _get_translation_prompt helper
# Delegate background task to app/services/ai/translation.py
# Update imports to shared/
```

- [ ] **Step 4: Commit**

```bash
git add app/routers/ai_config.py app/routers/ai_chat.py app/routers/ai_translate.py
git commit -m "refactor: split ai.py into ai_config, ai_chat, ai_translate routers"
```

---

### Task 11: Merge reading routers + update auth router imports

**Files:**
- Create: `epub-tts-backend/app/routers/reading.py`
- Modify: `epub-tts-backend/app/routers/auth.py` — update imports to shared/

- [ ] **Step 1: Create routers/reading.py**

Merge `reading_progress.py` (30 lines) and `reading_stats.py` (52 lines) into one file:

```python
# app/routers/reading.py
from fastapi import APIRouter, Depends, Query
from app.middleware.auth import get_current_user
from shared.database import get_db
from shared.models import Book
from app.services.reading_progress_service import ReadingProgressService
from app.services.reading_stats_service import ReadingStatsService

router = APIRouter(prefix="/reading", tags=["reading"])

# --- Progress ---
# GET /progress/{book_id} — copy from reading_progress.py
# PUT /progress/{book_id} — copy from reading_progress.py

# --- Stats ---
# POST /stats/heartbeat — copy from reading_stats.py
# GET /stats/heatmap — copy from reading_stats.py
# GET /stats/books — copy from reading_stats.py
# GET /stats/summary — copy from reading_stats.py
```

- [ ] **Step 2: Update auth.py imports**

Change `from app.models.user import ...` to `from shared.schemas.auth import ...`:

```python
# app/routers/auth.py line 5:
# Before: from app.models.user import UserCreate, UserLogin, UserResponse, Token, ThemeIn, ThemeOut, FontSizeIn, FontSizeOut
# After:  from shared.schemas.auth import UserCreate, UserLogin, UserResponse, Token, ThemeIn, ThemeOut, FontSizeIn, FontSizeOut, VerifyRequest, ResendRequest
```

Also remove the inline `VerifyRequest` and `ResendRequest` class definitions (now in shared/schemas/auth.py).

- [ ] **Step 3: Commit**

```bash
git add app/routers/reading.py app/routers/auth.py
git commit -m "refactor: merge reading routers, update auth imports"
```

---

### Task 12: Update main.py to use new routers

**Files:**
- Modify: `epub-tts-backend/app/main.py`

- [ ] **Step 1: Update router imports and registration**

```python
# app/main.py
from contextlib import asynccontextmanager
from loguru import logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# New routers
from app.routers.auth import router as auth_router
from app.routers.books import router as books_router
from app.routers.tts import router as tts_router
from app.routers.tts_download import router as tts_download_router
from app.routers.tts_cache import router as tts_cache_router
from app.routers.tts_config import router as tts_config_router
from app.routers.voices import router as voices_router
from app.routers.ai_config import router as ai_config_router
from app.routers.ai_chat import router as ai_chat_router
from app.routers.ai_translate import router as ai_translate_router
from app.routers.reading import router as reading_router
from app.routers.highlights import router as highlights_router
from app.routers.files import router as files_router
from app.routers.index import router as index_router
from app.routers.tasks import router as tasks_router
import os


def _run_migrations():
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("[Database] Alembic migrations applied")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    yield


app = FastAPI(title="EPUB-TTS Backend", version="2.0.0", lifespan=lifespan)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("data/users", exist_ok=True)
os.makedirs("data/images", exist_ok=True)

app.mount("/images", StaticFiles(directory="data/images"), name="images")

# All routers under /api prefix
app.include_router(auth_router, prefix="/api")
app.include_router(books_router, prefix="/api")
app.include_router(tts_router, prefix="/api")
app.include_router(tts_download_router, prefix="/api")
app.include_router(tts_cache_router, prefix="/api")
app.include_router(tts_config_router, prefix="/api")
app.include_router(voices_router, prefix="/api")
app.include_router(ai_config_router, prefix="/api")
app.include_router(ai_chat_router, prefix="/api")
app.include_router(ai_translate_router, prefix="/api")
app.include_router(reading_router, prefix="/api")
app.include_router(highlights_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(index_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "EPUB-TTS Backend is running", "docs": "/docs"}
```

- [ ] **Step 2: Verify app starts**

Run: `cd epub-tts-backend && python -c "from app.main import app; print('Routes:', len(app.routes))"`

Expected: prints route count without import errors.

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "refactor: update main.py to use new router structure"
```

---

## Phase 4: Admin Backend

### Task 13: Switch admin-backend to shared/ imports

**Files:**
- Modify: `admin-backend/app/main.py` — add sys.path for shared
- Delete content of: `admin-backend/app/models.py` → re-export from shared
- Delete content of: `admin-backend/app/database.py` → re-export from shared
- Delete content of: `admin-backend/app/config.py` → re-export from shared
- Delete content of: `admin-backend/app/redis_client.py` → re-export from shared

- [ ] **Step 1: Add sys.path setup in admin main.py**

Add at the top of `admin-backend/app/main.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'epub-tts-backend'))
```

- [ ] **Step 2: Replace admin models.py**

```python
# admin-backend/app/models.py
from shared.models import Base, User, Book, ReadingStat, Highlight, SystemSetting

__all__ = ["Base", "User", "Book", "ReadingStat", "Highlight", "SystemSetting"]
```

- [ ] **Step 3: Replace admin database.py**

```python
# admin-backend/app/database.py
from shared.database import engine, SessionLocal, get_db

__all__ = ["engine", "SessionLocal", "get_db"]
```

- [ ] **Step 4: Replace admin config.py**

```python
# admin-backend/app/config.py
from shared.config import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
```

- [ ] **Step 5: Replace admin redis_client.py**

```python
# admin-backend/app/redis_client.py
from shared.redis_client import get_redis

__all__ = ["get_redis"]
```

- [ ] **Step 6: Update admin Dockerfile**

Add COPY for shared/:

```dockerfile
# In admin-backend/Dockerfile, add before the CMD:
COPY ../epub-tts-backend/shared /app/shared
```

Or use docker-compose build context adjustment.

- [ ] **Step 7: Verify admin starts**

Run: `cd admin-backend && PYTHONPATH=../epub-tts-backend python -c "from app.main import app; print('OK')"`

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add admin-backend/
git commit -m "refactor: switch admin-backend to shared/ imports"
```

---

## Phase 5: Frontend API Path Updates

### Task 14: Update main frontend API paths

**Files:**
- Modify: `epub-tts-frontend/src/api/services.ts`
- Modify: `epub-tts-frontend/src/api/tts.ts`
- Modify: `epub-tts-frontend/src/contexts/AuthContext.tsx`
- Modify: `epub-tts-frontend/src/contexts/ThemeContext.tsx`
- Modify: `epub-tts-frontend/src/pages/BookReader.tsx`
- Modify: `epub-tts-frontend/src/components/player/Controls.tsx`
- Modify: `epub-tts-frontend/src/components/player/TasksPanel.tsx`

The API path mapping (old → new):

| Old Path | New Path | Change? |
|----------|----------|---------|
| `/tts/speak` | `/tts/speak` | No |
| `/tts/prefetch` | `/tts/prefetch` | No |
| `/tts/config` | `/tts/config` | No |
| `/tts/providers/status` | `/tts/providers/status` | No |
| `/tts/voices` | `/voices` | **Yes** |
| `/tts/voices/edge` | `/voices/edge` | **Yes** |
| `/tts/voices/minimax` | `/voices/minimax` | **Yes** |
| `/tts/voices/clone` | `/voices/clone` | **Yes** |
| `/tts/voices/cloned` | `/voices/cloned` | **Yes** |
| `/tts/voices/cloned/{id}` | `/voices/cloned/{id}` | **Yes** |
| `/tts/voice-preferences` | `/voices/preferences` | **Yes** |
| `/tts/download/{uid}/{bid}/{fn}` | `/files/audio/{bid}/{fn}` | **Yes** |
| `/reading-progress/{bookId}` | `/reading/progress/{bookId}` | **Yes** |
| `/reading-stats/heartbeat` | `/reading/stats/heartbeat` | **Yes** |
| `/reading-stats/heatmap` | `/reading/stats/heatmap` | **Yes** |
| `/reading-stats/books` | `/reading/stats/books` | **Yes** |
| `/reading-stats/summary` | `/reading/stats/summary` | **Yes** |
| `/tts/download` (POST) | `/tts/download/chapter` | **Yes** |
| `/tts/download/chapter` (POST) | `/tts/download/chapter/smart` | **Yes** |

- [ ] **Step 1: Update tts.ts voice endpoints**

In `epub-tts-frontend/src/api/tts.ts`, find-and-replace:
- `/tts/voices` → `/voices` (for the base endpoint)
- `/tts/voices/edge` → `/voices/edge`
- `/tts/voices/minimax` → `/voices/minimax`
- `/tts/voices/clone` → `/voices/clone`
- `/tts/voices/cloned` → `/voices/cloned`
- `/tts/voice-preferences` → `/voices/preferences`

- [ ] **Step 2: Update services.ts reading endpoints**

In `epub-tts-frontend/src/api/services.ts`, find-and-replace:
- `/reading-progress/` → `/reading/progress/`
- `/reading-stats/` → `/reading/stats/`

- [ ] **Step 3: Update services.ts download endpoints**

In services.ts and Controls.tsx:
- `/tts/download` (POST for chapter) → `/tts/download/chapter`
- Any references to `/tts/download/{uid}/{bid}/{fn}` → `/files/audio/{bid}/{fn}`

- [ ] **Step 4: Update any remaining scattered references**

Search all `.ts` and `.tsx` files for old API paths and update.

- [ ] **Step 5: Commit**

```bash
cd epub-tts-frontend
git add src/
git commit -m "refactor: update frontend API paths to match new backend structure"
```

---

### Task 15: Update admin frontend (if needed)

**Files:**
- Verify: `admin-frontend/src/api/services.ts`

Admin frontend uses `/api/admin/` prefix. The admin backend router paths are NOT changing, so admin frontend should need zero changes. Verify this.

- [ ] **Step 1: Verify admin paths unchanged**

Check that all admin endpoints (`/auth/login`, `/users/`, `/dashboard/*`, `/settings/`) are unchanged.

- [ ] **Step 2: Commit (only if changes needed)**

```bash
# Only if changes were needed
cd admin-frontend && git add src/ && git commit -m "refactor: update admin frontend API paths"
```

---

## Phase 6: Cleanup

### Task 16: Remove old files and compatibility shims

**Files:**
- Delete: `epub-tts-backend/app/api.py` (replaced by split routers)
- Delete: `epub-tts-backend/app/routers/ai.py` (replaced by ai_config/ai_chat/ai_translate)
- Delete: `epub-tts-backend/app/routers/reading_progress.py` (merged into reading.py)
- Delete: `epub-tts-backend/app/routers/reading_stats.py` (merged into reading.py)
- Update: all remaining `app.*` imports in services to use `shared.*` directly
- Update: all remaining router imports to use `shared.*` directly

- [ ] **Step 1: Delete old router files**

```bash
cd epub-tts-backend
rm app/api.py
rm app/routers/ai.py
rm app/routers/reading_progress.py
rm app/routers/reading_stats.py
```

- [ ] **Step 2: Update all remaining imports across services**

Go through each service file and router file. Replace:
- `from app.models.database import get_db` → `from shared.database import get_db`
- `from app.models.models import X` → `from shared.models import X`
- `from app.config import settings` → `from shared.config import settings`
- `from app.redis_client import get_redis` → `from shared.redis_client import get_redis`

Files to update:
- `app/middleware/auth.py`
- `app/middleware/rate_limit.py`
- `app/routers/auth.py`
- `app/routers/books.py`
- `app/routers/highlights.py`
- `app/routers/files.py`
- `app/routers/index.py`
- `app/services/book_service.py`
- `app/services/auth_service.py`
- `app/services/email_service.py`
- `app/services/highlight_service.py`
- `app/services/reading_progress_service.py`
- `app/services/reading_stats_service.py`
- `app/services/index_service.py`
- `app/services/system_settings.py`

- [ ] **Step 3: Remove compatibility shims**

Once all direct imports are updated, the shims are no longer needed. But keep `app/models/models.py` shim for safety (alembic versions may reference it in comments).

- [ ] **Step 4: Verify full app starts**

Run: `cd epub-tts-backend && python -c "from app.main import app; print('Routes:', len(app.routes))"`

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: cleanup old files, update all imports to shared/"
```

---

### Task 17: Update Docker configuration

**Files:**
- Modify: `docker-compose.yml`
- Modify: `epub-tts-backend/Dockerfile` (if exists)
- Modify: `admin-backend/Dockerfile`

- [ ] **Step 1: Update docker-compose build contexts**

Ensure both backends can access `shared/`:
- Main backend: shared/ is inside epub-tts-backend/, no changes needed
- Admin backend: needs shared/ copied in or mounted

```yaml
# docker-compose.yml — admin-backend service
admin-backend:
  build:
    context: .  # Change to repo root so Dockerfile can COPY shared/
    dockerfile: admin-backend/Dockerfile
```

- [ ] **Step 2: Update admin Dockerfile**

```dockerfile
# admin-backend/Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY admin-backend/requirements.txt .
RUN pip install -r requirements.txt
COPY epub-tts-backend/shared /app/shared
COPY admin-backend/app /app/app
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 3: Verify Docker builds**

```bash
docker-compose build backend admin-backend
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml admin-backend/Dockerfile
git commit -m "refactor: update Docker config for shared/ layer"
```

---

### Task 18: Final verification

- [ ] **Step 1: Start backend locally, verify /docs shows all routes**

```bash
cd epub-tts-backend && uvicorn app.main:app --reload
# Open http://localhost:8000/docs — verify all endpoints listed
```

- [ ] **Step 2: Run docker-compose up, verify both backends healthy**

```bash
docker-compose up -d
docker-compose ps  # All services should be healthy
```

- [ ] **Step 3: Smoke test key flows**

Manual verification:
1. Login/Register works
2. Book upload and reading works
3. TTS speak generates audio
4. AI chat streams response
5. Admin dashboard loads

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "refactor: backend restructure complete — verified"
```
