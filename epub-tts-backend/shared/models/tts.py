from sqlalchemy import Column, String, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from shared.models import Base


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
