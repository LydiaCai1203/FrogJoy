from sqlalchemy import Column, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from shared.models import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False, server_default="false")
    is_admin = Column(Boolean, default=False, server_default="false")
    is_active = Column(Boolean, default=True, server_default="true")
    created_at = Column(DateTime, server_default=func.now())
    last_login_at = Column(DateTime, nullable=True)
    avatar_url = Column(String, nullable=True)

    books = relationship("Book", back_populates="user")
    highlights = relationship("Highlight", back_populates="user")
    reading_stats = relationship("ReadingStat", back_populates="user")
    reading_progress = relationship("ReadingProgress", back_populates="user")
    ai_provider_configs = relationship("AIProviderConfig", back_populates="user")
    book_translations = relationship("BookTranslation", back_populates="user")
    tts_provider_config = relationship("TTSProviderConfig", back_populates="user", uselist=False)
    cloned_voices = relationship("ClonedVoice", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreferences", back_populates="user", uselist=False)
