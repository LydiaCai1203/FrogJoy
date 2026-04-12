"""
后台定时任务服务 - 管理 MiniMax 克隆音色保活等周期性任务
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger

from app.models.database import get_db
from app.models.models import ClonedVoice, TTSProviderConfig
from app.services.auth_service import AuthService
from app.services.voice_clone import VoiceCloneService


class CronService:
    """
    后台定时任务服务。

    使用方式：
        # 启动（通常在 FastAPI startup 事件中调用）
        from app.services.cron_service import cron_service
        asyncio.create_task(cron_service.start())

        # 停止（通常在 FastAPI shutdown 事件中调用）
        await cron_service.stop()
    """

    KEEPALIVE_THRESHOLD_HOURS = 23     # 克隆音色超过 23 小时则触发保活
    TICK_INTERVAL_SECONDS = 3600       # 每小时检查一次

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """启动定时任务循环（后台运行）"""
        if self._running:
            logger.warning("[Cron] Already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[Cron] Service started")

    async def stop(self) -> None:
        """停止定时任务循环"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[Cron] Service stopped")

    async def _loop(self) -> None:
        """主循环：每小时检查一次是否需要保活"""
        while self._running:
            try:
                await self._run_keepalive()
            except Exception as e:
                logger.error(f"[Cron] Keepalive task error: {e}")
            await asyncio.sleep(self.TICK_INTERVAL_SECONDS)

    async def _run_keepalive(self) -> None:
        """检查所有克隆音色，对超过阈值的使用者发送保活请求"""
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(hours=self.KEEPALIVE_THRESHOLD_HOURS)

        with get_db() as db:
            voices = (
                db.query(ClonedVoice)
                .order_by(ClonedVoice.user_id, ClonedVoice.created_at.asc())
                .all()
            )

        if not voices:
            return

        # 按用户分组，每用户只检查一个最老的音色
        seen_users = set()
        voices_to_check = []
        for v in voices:
            if v.user_id not in seen_users:
                seen_users.add(v.user_id)
                voices_to_check.append(v)

        logger.info(f"[Cron] Checking keepalive for {len(voices_to_check)} users with cloned voices")

        for voice in voices_to_check:
            try:
                created = voice.created_at or datetime.now(timezone.utc)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)

                # 用 last_used_at 判断保活需求（优先），没有则用 created_at
                check_time = voice.last_used_at or created
                if check_time.tzinfo is None:
                    check_time = check_time.replace(tzinfo=timezone.utc)

                if check_time > threshold:
                    # 距离上次使用不足 23 小时，跳过
                    continue

                # 获取该用户的 MiniMax API Key
                api_key, base_url = self._get_user_credentials(voice.user_id)
                if not api_key:
                    logger.warning(f"[Cron] No MiniMax API key for user {voice.user_id}, skip keepalive")
                    continue

                age_hours = (now - created).total_seconds() / 3600
                logger.info(f"[Cron] Sending keepalive ping for voice {voice.voice_id} (user={voice.user_id}, age={age_hours:.1f}h)")

                audio_data = await VoiceCloneService.generate_speech_minimax(
                    api_key=api_key,
                    text="啊",
                    voice_id=voice.voice_id,
                    speed=1.0,
                    pitch=0,
                    emotion="neutral",
                    base_url=base_url,
                    max_retries=1,
                )

                if audio_data:
                    # 更新 last_used_at
                    with get_db() as db:
                        db_voice = db.query(ClonedVoice).filter(
                            ClonedVoice.id == voice.id
                        ).first()
                        if db_voice:
                            db_voice.last_used_at = datetime.now(timezone.utc)
                            db.commit()
                    logger.info(f"[Cron] Keepalive successful for voice {voice.voice_id}, {len(audio_data)} bytes")
                else:
                    logger.warning(f"[Cron] Keepalive returned empty audio for voice {voice.voice_id}")

                # 避免请求过快，每个音色间隔 2 秒
                await asyncio.sleep(2)

            except Exception as e:
                logger.warning(f"[Cron] Keepalive failed for voice {voice.voice_id}: {e}")

    def _get_user_credentials(self, user_id: str) -> tuple[Optional[str], Optional[str]]:
        """获取用户的 MiniMax API Key，返回 (api_key, base_url)"""
        try:
            with get_db() as db:
                config = db.query(TTSProviderConfig).filter(
                    TTSProviderConfig.user_id == user_id
                ).first()
            if not config or not config.api_key_encrypted:
                return None, None
            api_key = AuthService.decrypt_api_key(config.api_key_encrypted)
            return api_key, config.base_url
        except Exception as e:
            logger.warning(f"[Cron] Failed to get credentials for user {user_id}: {e}")
            return None, None


# 全局单例
cron_service = CronService()

