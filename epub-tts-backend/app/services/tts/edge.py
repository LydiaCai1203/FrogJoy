import edge_tts
import re
from typing import List, Dict


DEFAULT_VOICES = {
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
}


def detect_language(text: str) -> str:
    if re.search(r'[\u4e00-\u9fff]', text):
        return "zh"
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text):
        return "ja"
    if re.search(r'[\uac00-\ud7af]', text):
        return "ko"
    return "en"


def get_default_voice(text: str) -> str:
    lang = detect_language(text)
    return DEFAULT_VOICES.get(lang, "en-US-JennyNeural")


async def get_voices() -> List[Dict[str, str]]:
    voices = await edge_tts.list_voices()
    return [
        {
            "name": v["ShortName"],
            "gender": v["Gender"],
            "lang": v["Locale"]
        }
        for v in voices
    ]
