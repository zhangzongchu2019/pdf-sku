"""
定时任务调度。对齐: Feedback 详设 §5

- 02:00 属性升级检查
- 03:00 阈值校准
- 06:00 审批超时提醒
- 每 30min SLA 锁扫描 + 对账

使用 asyncio 周期任务, Redis 分布式锁防重入。
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


class ScheduledTaskRunner:
    """定时任务运行器。"""

    def __init__(
        self,
        calibration_engine=None,
        promotion_checker=None,
        sla_scanner=None,
        lock_manager=None,
        reconciler=None,
        db_session_factory=None,
    ):
        self._calibration = calibration_engine
        self._promotion = promotion_checker
        self._sla = sla_scanner
        self._lock_mgr = lock_manager
        self._reconciler = reconciler
        self._db_factory = db_session_factory
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        """启动所有定时任务。"""
        self._running = True
        self._tasks = [
            asyncio.create_task(self._periodic_sla_scan()),
            asyncio.create_task(self._periodic_lock_scan()),
            asyncio.create_task(self._periodic_reconcile()),
            asyncio.create_task(self._daily_calibration()),
            asyncio.create_task(self._daily_promotion()),
            asyncio.create_task(self._daily_approval_sla()),
        ]
        logger.info("scheduled_tasks_started", count=len(self._tasks))

    async def stop(self) -> None:
        """停止所有定时任务。"""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("scheduled_tasks_stopped")

    async def _periodic_sla_scan(self) -> None:
        """每 5 分钟 SLA 熔断扫描。"""
        while self._running:
            try:
                await asyncio.sleep(300)
                if self._sla and self._db_factory:
                    async with self._db_factory() as db:
                        async with db.begin():
                            await self._sla.scan_escalation(db)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("sla_scan_error", error=str(e))

    async def _periodic_lock_scan(self) -> None:
        """每 2 分钟锁超时扫描。"""
        while self._running:
            try:
                await asyncio.sleep(120)
                if self._lock_mgr and self._db_factory:
                    async with self._db_factory() as db:
                        async with db.begin():
                            await self._lock_mgr.scan_expired_locks(db)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("lock_scan_error", error=str(e))

    async def _periodic_reconcile(self) -> None:
        """每 30 分钟对账。"""
        while self._running:
            try:
                await asyncio.sleep(1800)
                if self._reconciler and self._db_factory:
                    async with self._db_factory() as db:
                        async with db.begin():
                            await self._reconciler.reconcile(db)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("reconcile_error", error=str(e))

    async def _daily_calibration(self) -> None:
        """每日 03:00 校准。"""
        while self._running:
            try:
                await self._sleep_until_hour(3)
                if self._calibration and self._db_factory:
                    async with self._db_factory() as db:
                        async with db.begin():
                            await self._calibration.check_and_calibrate(db)
                            logger.info("daily_calibration_done")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("daily_calibration_error", error=str(e))

    async def _daily_promotion(self) -> None:
        """每日 02:00 属性升级。"""
        while self._running:
            try:
                await self._sleep_until_hour(2)
                if self._promotion and self._db_factory:
                    async with self._db_factory() as db:
                        async with db.begin():
                            candidates = await self._promotion.check_promotions(db)
                            logger.info("daily_promotion_done",
                                        candidates=len(candidates))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("daily_promotion_error", error=str(e))

    async def _daily_approval_sla(self) -> None:
        """每日 06:00 审批超时提醒。"""
        while self._running:
            try:
                await self._sleep_until_hour(6)
                if self._calibration and self._db_factory:
                    async with self._db_factory() as db:
                        async with db.begin():
                            reminded = await self._calibration.check_approval_sla(db)
                            if reminded:
                                logger.info("approval_sla_reminded", count=reminded)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("approval_sla_error", error=str(e))

    @staticmethod
    async def _sleep_until_hour(target_hour: int) -> None:
        """睡到下一个目标小时。"""
        now = datetime.now(timezone.utc)
        target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target = target.replace(day=target.day + 1)
        delta = (target - now).total_seconds()
        await asyncio.sleep(max(60, delta))
