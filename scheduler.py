import asyncio
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from astrbot.api import logger
import pytz


class WeatherScheduler:
    """定时任务管理器"""

    def __init__(self, timezone: str = "Asia/Shanghai"):
        self.timezone = pytz.timezone(timezone_str)
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        self._job_id = "weather_daily_push"
        self._callback: Optional[Callable] = None
        self._push_time: Optional[str] = None

    def set_callback(self, callback: Callable):
        self._callback = callback
        logger.info("[Scheduler] 回调函数已设置")

    def update_schedule(self, push_time: str):
        """更新或创建每日定时任务"""
        self._push_time = push_time
        logger.info(f"[Scheduler] 更新定时任务，目标时间: {push_time}")

        # 移除现有任务
        if self._job_id in [job.id for job in self.scheduler.get_jobs()]:
            self.scheduler.remove_job(self._job_id)
            logger.info(f"[Scheduler] 已移除旧任务 {self._job_id}")

        if not push_time or not self._callback:
            logger.warning(f"[Scheduler] 配置不完整，跳过任务创建")
            return

        try:
            hour, minute = map(int, push_time.split(":"))
            # 显式指定时区，避免环境差异
            trigger = CronTrigger(hour=hour, minute=minute, timezone=self.timezone)

            now = datetime.now(self.timezone)
            next_run = trigger.get_next_fire_time(None, now)
            logger.info(f"[Scheduler] Cron: 每天 {hour:02d}:{minute:02d}, 预计下次: {next_run}")

            self.scheduler.add_job(
                self._execute_callback,
                trigger,
                id=self._job_id,
                name="天气每日推送",
                replace_existing=True
            )
            logger.info(f"[Scheduler] ✅ 定时推送已设置: 每天 {push_time}")
        except Exception as e:
            logger.error(f"[Scheduler] ❌ 设置定时任务失败: {e}", exc_info=True)

    async def _execute_callback(self):
        """执行回调函数（由调度器调用）"""
        logger.info(f"[Scheduler] 🚀 定时推送触发，当前时间: {datetime.now(self.timezone)}")
        if self._callback:
            try:
                await self._callback()
                logger.info("[Scheduler] ✅ 定时推送执行成功")
            except Exception as e:
                logger.error(f"[Scheduler] ❌ 定时推送执行失败: {e}", exc_info=True)
        else:
            logger.error("[Scheduler] ❌ 回调函数为空")

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("[Scheduler] 调度器已启动")
        else:
            logger.info("[Scheduler] 调度器已在运行中")

    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("[Scheduler] 调度器已关闭")
