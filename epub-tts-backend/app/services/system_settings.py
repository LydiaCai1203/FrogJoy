import time
from typing import Any

from shared.database import get_db
from shared.models import SystemSetting

_cache: dict[str, str] = {}
_cache_ts: float = 0.0
_CACHE_TTL = 60  # seconds


def _refresh_cache() -> None:
    global _cache, _cache_ts
    now = time.time()
    if _cache and now - _cache_ts < _CACHE_TTL:
        return
    with get_db() as db:
        rows = db.query(SystemSetting).all()
        _cache = {r.key: r.value for r in rows}
    _cache_ts = now


def get_system_setting(key: str, default: Any = None) -> str | None:
    _refresh_cache()
    return _cache.get(key, default)


def get_system_setting_int(key: str, default: int) -> int:
    val = get_system_setting(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def get_system_setting_bool(key: str, default: bool) -> bool:
    val = get_system_setting(key)
    if val is None:
        return default
    return val.lower() in ("true", "1", "yes")
