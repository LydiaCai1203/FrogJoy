from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from shared.models.user import User
from shared.models.book import Book
from shared.models.highlight import Highlight
from shared.models.reading import ReadingStat, ReadingProgress
from shared.models.ai import AIProviderConfig, BookTranslation
from shared.models.tts import TTSProviderConfig, ClonedVoice
from shared.models.preferences import UserPreferences
from shared.models.index import IndexedBook, IndexedParagraph
from shared.models.concept import Concept, ConceptOccurrence, ConceptEvidence
from shared.models.system import SystemSetting

__all__ = [
    "Base",
    "User", "Book", "Highlight",
    "ReadingStat", "ReadingProgress",
    "AIProviderConfig", "BookTranslation",
    "TTSProviderConfig", "ClonedVoice",
    "UserPreferences",
    "IndexedBook", "IndexedParagraph",
    "Concept", "ConceptOccurrence", "ConceptEvidence",
    "SystemSetting",
]
