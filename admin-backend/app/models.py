# Models now live in shared/ (epub-tts-backend)
from shared.models import Base, User, Book, ReadingStat, Highlight, SystemSetting, UserPreferences
__all__ = ["Base", "User", "Book", "ReadingStat", "Highlight", "SystemSetting", "UserPreferences"]
