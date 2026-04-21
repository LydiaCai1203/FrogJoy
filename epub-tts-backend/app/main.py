import sys
import logging
from contextlib import asynccontextmanager
from loguru import logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers.auth import router as auth_router
from app.routers.books import router as books_router
from app.routers.tts import router as tts_router
from app.routers.tts_download import router as tts_download_router
from app.routers.tts_cache import router as tts_cache_router
from app.routers.tts_config import router as tts_config_router
from app.routers.voices import router as voices_router
from app.routers.ai_config import router as ai_config_router
from app.routers.ai_chat import router as ai_chat_router
from app.routers.ai_translate import router as ai_translate_router
from app.routers.reading import router as reading_router
from app.routers.highlights import router as highlights_router
from app.routers.files import router as files_router
from app.routers.index import router as index_router
from app.routers.tasks import router as tasks_router
import os

# ── Loguru 配置 ─────────────────────────────────────────────
logger.remove()

# 控制台：简洁彩色
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> <level>{level: <7}</level> <level>{message}</level>",
    level="DEBUG",
)

# 文件：完整格式，按天轮转，保留 30 天
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <7} | {message}",
    level="DEBUG",
    rotation="00:00",
    retention="30 days",
    encoding="utf-8",
)

# 拦截 uvicorn / sqlalchemy 标准库日志 → loguru
class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())

for _name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
    logging.getLogger(_name).handlers = [_InterceptHandler()]
    logging.getLogger(_name).propagate = False


def _run_migrations():
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("[Database] Alembic migrations applied")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    yield


app = FastAPI(title="EPUB-TTS Backend", version="1.0.0", lifespan=lifespan)

# CORS Configuration
origins = [
    "http://localhost:5173",  # Vite Dev Server
    "http://127.0.0.1:5173",
    "*"  # Allow all for local dev convenience
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure data directories exist
os.makedirs("data/users", exist_ok=True)
os.makedirs("data/images", exist_ok=True)

# Mount static files for images (kept as-is)
app.mount("/images", StaticFiles(directory="data/images"), name="images")

# Include API Routers
app.include_router(auth_router, prefix="/api")
app.include_router(books_router, prefix="/api")
app.include_router(tts_router, prefix="/api")
app.include_router(tts_download_router, prefix="/api")
app.include_router(tts_cache_router, prefix="/api")
app.include_router(tts_config_router, prefix="/api")
app.include_router(voices_router, prefix="/api")
app.include_router(ai_config_router, prefix="/api")
app.include_router(ai_chat_router, prefix="/api")
app.include_router(ai_translate_router, prefix="/api")
app.include_router(reading_router, prefix="/api")
app.include_router(highlights_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(index_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "EPUB-TTS Backend is running", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
