#!/bin/bash
set -e

echo "[Cron] Starting cron service..."

python -c "
import asyncio
from app.services.cron_service import cron_service

async def main():
    await cron_service.start()
    # 保持进程运行，等待后台任务
    while cron_service._running:
        await asyncio.sleep(60)

asyncio.run(main())
"
