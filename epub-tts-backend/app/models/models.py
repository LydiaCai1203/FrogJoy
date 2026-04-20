from sqlalchemy import (
    Column, String, Integer, Boolean, Text, DateTime, ForeignKey, Index,
    UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


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
    ai_model_config = relationship("AIModelConfig", back_populates="user", uselist=False)
    ai_preferences = relationship("UserAIPreferences", back_populates="user", uselist=False)
    theme_preferences = relationship("UserThemePreferences", back_populates="user", uselist=False)
    book_translations = relationship("BookTranslation", back_populates="user")
    tts_provider_config = relationship("TTSProviderConfig", back_populates="user", uselist=False)
    voice_preferences = relationship("VoicePreferences", back_populates="user", uselist=False)
    cloned_voices = relationship("ClonedVoice", back_populates="user", cascade="all, delete-orphan")
    user_feature_setup = relationship("UserFeatureSetup", back_populates="user", uselist=False)


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


class ReadingStat(Base):
    __tablename__ = "reading_stats"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    date = Column(String, nullable=False)
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


class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    # Chat / Ask AI config
    provider_type = Column(String, nullable=False, default="openai-chat")
    base_url = Column(String, nullable=False)
    api_key_encrypted = Column(String, nullable=False)
    model = Column(String, nullable=False)
    # Translation-specific config
    translation_provider_type = Column(String, nullable=True)
    translation_base_url = Column(String, nullable=True)
    translation_api_key_encrypted = Column(String, nullable=True)
    translation_model = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class UserAIPreferences(Base):
    __tablename__ = "user_ai_preferences"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    enabled_ask_ai = Column(Boolean, default=False)
    enabled_translation = Column(Boolean, default=False)
    translation_mode = Column(String, default="current-page")
    source_lang = Column(String, default="Auto")
    target_lang = Column(String, default="Chinese")
    translation_prompt = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


class UserThemePreferences(Base):
    __tablename__ = "user_theme_preferences"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    theme = Column(String, default="eye-care")
    font_size = Column(Integer, default=18)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="theme_preferences")


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


class TTSProviderConfig(Base):
    """TTS Provider configuration per user"""
    __tablename__ = "tts_provider_configs"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    provider_type = Column(String, nullable=False, default="edge-tts")  # "edge-tts" | "minimax-tts"
    base_url = Column(String, nullable=True)  # MiniMax uses this
    api_key_encrypted = Column(String, nullable=True)  # MiniMax uses this
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="tts_provider_config")


class ClonedVoice(Base):
    """Cloned voice samples per user"""
    __tablename__ = "cloned_voices"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    voice_id = Column(String, nullable=False)  # Voice ID from MiniMax API
    name = Column(String, nullable=False)  # User-defined name
    audio_sample_path = Column(String, nullable=False)  # Stored sample file path
    lang = Column(String, default="zh")
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="cloned_voices")

    __table_args__ = (
        Index("idx_cloned_voices_user", "user_id"),
    )


class VoicePreferences(Base):
    """Voice selection preferences per user"""
    __tablename__ = "voice_preferences"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    active_voice_type = Column(String, default="edge")  # "edge" | "minimax" | "cloned"
    active_edge_voice = Column(String, default="zh-CN-XiaoxiaoNeural")
    active_minimax_voice = Column(String, nullable=True)
    active_cloned_voice_id = Column(String, nullable=True)
    speed = Column(Integer, default=100)  # 50-200
    pitch = Column(Integer, default=0)  # -50 to 50
    emotion = Column(String, default="neutral")  # neutral, warm, excited, serious, suspense
    audio_persistent = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="voice_preferences")


class UserFeatureSetup(Base):
    """Tracks which features have been configured by user"""
    __tablename__ = "user_feature_setup"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    ai_chat_configured = Column(Boolean, default=False)
    ai_translation_configured = Column(Boolean, default=False)
    voice_selection_configured = Column(Boolean, default=False)
    voice_synthesis_configured = Column(Boolean, default=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="user_feature_setup")


class SystemSetting(Base):
    """System-wide settings managed via admin panel"""
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# =============================================================================
# Index Layer: Book Language Server 的段落级索引
# 设计文档: docs/book-as-indexed-knowledge-base.md §6
#
# 当前只实现 v0: paragraphs (段落稳定 ID + 原文)
# concepts / occurrences / relations 等在 Extractor (LLM) 接入后追加
# =============================================================================

class IndexedBook(Base):
    """
    每用户每本书的索引元信息。

    一本书对应 Book 表里一条记录, 其"索引状态"挂在这张表上:
      - 还没扫?  不在此表
      - 扫过?    status='parsed', 可以查询 paragraphs
      - 扫失败?  status='failed', 看 error_message

    后续 Extractor (LLM) 会往此表加 extractor_status 字段。
    """
    __tablename__ = "indexed_books"

    book_id = Column(String, ForeignKey("books.id"), primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)

    # 书的稳定指纹 (来自 paragraph_id.book_id), 用于跨书识别同一部作品
    book_fingerprint = Column(String, nullable=False)

    # 统计
    total_chapters = Column(Integer, nullable=False, default=0)
    total_paragraphs = Column(Integer, nullable=False, default=0)

    # 状态: pending / parsing / parsed / failed
    status = Column(String, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)

    # 索引版本 (schema 演进)
    index_version = Column(String, nullable=False, default="v0")

    # 时间戳
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
    """
    段落级索引条目。

    id = paragraph_id (见 app/parsers/paragraph_id.py)
      格式: {book_id}:{chapter_fp}:{content_fp}
      稳定、确定性, 同一段落不同次解析产生相同 id。

    每用户每本书的段落是独立行 (因 Book 本身是 per-user 的)。
    未来若要跨用户去重, 可在 book_fingerprint 层聚合。
    """
    __tablename__ = "indexed_paragraphs"

    id = Column(String, primary_key=True)                                    # paragraph_id
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)

    # 章节
    chapter_idx = Column(Integer, nullable=False)
    chapter_title = Column(String, nullable=True)
    chapter_fp = Column(String, nullable=False)

    # 章内位置
    para_idx_in_chapter = Column(Integer, nullable=False)

    # 内容 (原文)
    text = Column(Text, nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # 主要查询模式: 按 (user, book) 拉段落, 或 (user, book, chapter)
        Index("idx_iparagraphs_user_book", "user_id", "book_id"),
        Index("idx_iparagraphs_user_book_chapter",
              "user_id", "book_id", "chapter_idx"),
    )
