from pydantic import BaseModel
from typing import Optional, List


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "en-US-ChristopherNeural"
    voice_type: Optional[str] = "edge"  # "edge" | "minimax" | "cloned"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    volume: Optional[float] = 1.0
    book_id: Optional[str] = None
    chapter_href: Optional[str] = None
    paragraph_index: Optional[int] = None
    is_translated: Optional[bool] = False


class PrefetchRequest(BaseModel):
    book_id: str
    chapter_href: str
    sentences: List[str]
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    voice_type: Optional[str] = "edge"  # "edge" | "minimax" | "cloned"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    start_index: int
    end_index: int


class DownloadRequest(BaseModel):
    sentences: List[str]
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    filename: Optional[str] = "chapter"


class ChapterDownloadRequest(BaseModel):
    book_id: str
    chapter_href: str
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
    filename: Optional[str] = "chapter"


class BookDownloadRequest(BaseModel):
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0


class BookDownloadZipRequest(BaseModel):
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[float] = 1.0
    pitch: Optional[float] = 1.0
