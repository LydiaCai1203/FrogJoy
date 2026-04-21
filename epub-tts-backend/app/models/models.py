from shared.models import (
    Base, User, Book, Highlight,
    ReadingStat, ReadingProgress,
    AIProviderConfig, BookTranslation,
    TTSProviderConfig, ClonedVoice,
    UserPreferences,
    IndexedBook, IndexedParagraph,
    SystemSetting,
)

# Backward-compat aliases
AIModelConfig = AIProviderConfig
VoicePreferences = UserPreferences
UserThemePreferences = UserPreferences
UserAIPreferences = UserPreferences
UserFeatureSetup = None  # Deleted — code referencing this needs updating
