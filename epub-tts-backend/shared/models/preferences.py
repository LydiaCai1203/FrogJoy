from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from shared.models import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    # Theme
    theme = Column(String, default="eye-care")
    font_size = Column(Integer, default=18)
    # Voice
    active_voice_type = Column(String, default="edge")
    active_edge_voice = Column(String, default="zh-CN-XiaoxiaoNeural")
    active_minimax_voice = Column(String, nullable=True)
    active_cloned_voice_id = Column(String, nullable=True)
    speed = Column(Integer, default=100)
    pitch = Column(Integer, default=0)
    emotion = Column(String, default="neutral")
    audio_persistent = Column(Boolean, default=False)
    # AI
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
