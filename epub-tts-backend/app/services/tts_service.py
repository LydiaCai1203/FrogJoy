# Compatibility shim
from app.services.tts.cache import AudioCache
from app.services.tts.memory import AudioMemoryCache, memory_cache, _tmp_audio_dir
from app.services.tts.facade import TTSFacade as TTSService
__all__ = ["AudioCache", "AudioMemoryCache", "memory_cache", "TTSService", "_tmp_audio_dir"]
