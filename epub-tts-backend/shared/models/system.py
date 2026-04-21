from sqlalchemy import Column, String, DateTime, func
from shared.models import Base


class SystemSetting(Base):
    """System-wide settings managed via admin panel"""
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
