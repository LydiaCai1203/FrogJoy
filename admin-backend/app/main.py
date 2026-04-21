import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'epub-tts-backend'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.dashboard import router as dashboard_router
from app.routers.settings import router as settings_router

app = FastAPI(title="BookReader Admin API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/admin")
app.include_router(users_router, prefix="/api/admin")
app.include_router(dashboard_router, prefix="/api/admin")
app.include_router(settings_router, prefix="/api/admin")


@app.get("/")
async def root():
    return {"message": "BookReader Admin API is running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
