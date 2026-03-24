from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api import router
from app.routers.auth import router as auth_router
from app.routers.books import router as books_router
from app.routers.files import router as files_router
from app.models.database import init_db
import os

app = FastAPI(title="EPUB-TTS Backend", version="1.0.0")

# Initialize database
init_db()

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
app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(books_router, prefix="/api")
app.include_router(files_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "EPUB-TTS Backend is running", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
