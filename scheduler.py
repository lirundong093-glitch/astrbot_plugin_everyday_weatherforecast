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
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone(timezone))
        self._job_id = "weather_daily_push"
        self._callback: Optional[Callable] = None
        self._push_time: Optional[str] = None

    def set_callback(self, callback: Callable):
        """设置定时推送回调函数"""
        self._callback = callback

    def update_schedule(self, push_time: str):
        """
        更新定时任务
        push_time: HH:MM 格式，如 "08:00"
        """
        self._push_time = push_time

        # 移除旧任务
        if self._job_id in [job.id for job in self.scheduler.get_jobs()]:
            self.scheduler.remove_job(self._job_id)

        if not push_time or not self._callback:
            logger.warning("定时推送未配置或回调函数未设置")
            return

        try:
            hour, minute = map(int, push_time.split(":"))

            # 添加Cron任务
            self.scheduler.add_job(
                self._execute_callback,
                CronTrigger(hour=hour, minute=minute),
                id=self._job_id,
                name="天气每日推送",
                replace_existing=True
            )
            logger.info(f"定时推送已设置: 每天 {push_time}")
        except Exception as e:
            logger.error(f"设置定时任务失败: {e}")

    async def _execute_callback(self):
        """执行回调函数"""
        if self._callback:
            try:
                await self._callback()
                logger.info("定时推送执行成功")
            except Exception as e:
                logger.error(f"定时推送执行失败: {e}")

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("定时任务调度器已启动")

    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("定时任务调度器已关闭")