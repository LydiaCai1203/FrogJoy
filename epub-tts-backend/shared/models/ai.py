from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import relationship
from shared.models import Base


class AIProviderConfig(Base):
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
