from fastapi import APIRouter, Depends
from app.dependencies import get_admin_user
from app.schemas.settings import SystemSettings, SystemSettingsUpdate
from app.database import get_db
from app.models import SystemSetting

router = APIRouter(prefix="/settings", tags=["admin-settings"])


def _load_settings() -> SystemSettings:
    with get_db() as db:
        rows = db.query(SystemSetting).all()
        data = {r.key: r.value for r in rows}
    return SystemSettings(
        guest_rate_limit_tts=int(data.get("guest_rate_limit_tts", 5)),
        guest_rate_limit_translation=int(data.get("guest_rate_limit_translation", 1)),
        guest_rate_limit_chat=int(data.get("guest_rate_limit_chat", 1)),
        default_tts_provider=data.get("default_tts_provider", "edge-tts"),
        default_theme=data.get("default_theme", "eye-care"),
        default_font_size=int(data.get("default_font_size", 18)),
        allow_registration=data.get("allow_registration", "true").lower() in ("true", "1", "yes"),
    )


def _save_settings(s: SystemSettings):
    mapping = {
        "guest_rate_limit_tts": str(s.guest_rate_limit_tts),
        "guest_rate_limit_translation": str(s.guest_rate_limit_translation),
        "guest_rate_limit_chat": str(s.guest_rate_limit_chat),
        "default_tts_provider": s.default_tts_provider,
        "default_theme": s.default_theme,
        "default_font_size": str(s.default_font_size),
        "allow_registration": str(s.allow_registration).lower(),
    }
    with get_db() as db:
        for key, value in mapping.items():
            row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if row:
                row.value = value
            else:
                db.add(SystemSetting(key=key, value=value))
        db.commit()


@router.get("/", response_model=SystemSettings)
async def get_settings(_admin: str = Depends(get_admin_user)):
    return _load_settings()


@router.put("/", response_model=SystemSettings)
async def update_settings(data: SystemSettingsUpdate, _admin: str = Depends(get_admin_user)):
    current = _load_settings()
    update_data = data.model_dump(exclude_unset=True)
    updated = current.model_copy(update=update_data)
    _save_settings(updated)
    return updated
