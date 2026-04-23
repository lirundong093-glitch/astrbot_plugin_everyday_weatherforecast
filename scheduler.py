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
        logger.info("[Scheduler] 回调函数已设置")

    def update_schedule(self, push_time: str):
        """
        更新定时任务
        push_time: HH:MM 格式，如 "08:00"
        """
        self._push_time = push_time
        logger.info(f"[Scheduler] 收到更新定时任务请求，目标时间: {push_time}")

        # 移除旧任务
        current_jobs = self.scheduler.get_jobs()
        logger.info(f"[Scheduler] 当前调度器中的任务数量: {len(current_jobs)}")
        for job in current_jobs:
            logger.info(f"[Scheduler] 已有任务 ID: {job.id}, 下次运行: {job.next_run_time}")

        if self._job_id in [job.id for job in current_jobs]:
            self.scheduler.remove_job(self._job_id)
            logger.info(f"[Scheduler] 已移除旧任务 {self._job_id}")

        if not push_time or not self._callback:
            logger.warning(f"[Scheduler] 定时推送未配置 (push_time={push_time}) 或回调函数未设置")
            return

        try:
            hour, minute = map(int, push_time.split(":"))
            trigger = CronTrigger(hour=hour, minute=minute)
            # 计算下次运行时间用于调试
            now = datetime.now(pytz.timezone("Asia/Shanghai"))
            next_run = trigger.get_next_fire_time(None, now)
            logger.info(f"[Scheduler] Cron 表达式: 每天 {hour:02d}:{minute:02d}, 预计下次运行: {next_run}")

            self.scheduler.add_job(
                self._execute_callback,
                trigger,
                id=self._job_id,
                name="天气每日推送",
                replace_existing=True
            )
            logger.info(f"[Scheduler] ✅ 定时推送已成功设置: 每天 {push_time}")
        except Exception as e:
            logger.error(f"[Scheduler] ❌ 设置定时任务失败: {e}", exc_info=True)

    async def _execute_callback(self):
        """执行回调函数"""
        logger.info(f"[Scheduler] 🚀 定时推送触发，当前时间: {datetime.now()}")
        if self._callback:
            try:
                await self._callback()
                logger.info("[Scheduler] ✅ 定时推送执行成功")
            except Exception as e:
                logger.error(f"[Scheduler] ❌ 定时推送执行失败: {e}", exc_info=True)
        else:
            logger.error("[Scheduler] ❌ 回调函数为空，无法执行推送")

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("[Scheduler] 定时任务调度器已启动")
        else:
            logger.info("[Scheduler] 调度器已在运行中")

    def shutdown(self):
        """关闭调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("[Scheduler] 定时任务调度器已关闭")
