# ops_channel/ops_scheduler.py
"""调度器主进程：Cron 触发 → Agent 执行 → Delivery 投递。"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class OpsScheduler:
    def __init__(self, runner, router, job_store, jobs: list | None = None, config: dict | None = None):
        self._runner = runner
        self._router = router
        self._job_store = job_store
        self._jobs: dict[str, Any] = {}
        self._apscheduler = None
        self._config = config or {}
        if jobs:
            for job in jobs:
                self._jobs[job.job_id] = job

    def register_job(self, job) -> None:
        self._jobs[job.job_id] = job

    def start(self) -> None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
        except ImportError:
            logger.warning("apscheduler not installed, cron scheduling disabled")
            return

        self._apscheduler = AsyncIOScheduler(timezone=self._config.get("timezone", "Asia/Shanghai"))
        jobs_config = self._config.get("jobs", {})

        for job_id, job in self._jobs.items():
            if not job.enabled:
                continue
            if job.trigger.type.value == "cron" and job.trigger.cron_expr:
                job_cfg = jobs_config.get(job_id, {})
                if not job_cfg.get("enabled", True):
                    continue
                parts = job.trigger.cron_expr.split()
                self._apscheduler.add_job(
                    self._execute_job, "cron", args=[job_id, {}], id=job_id,
                    minute=parts[0], hour=parts[1],
                )
                logger.info("Scheduled job %s: cron=%s", job_id, job.trigger.cron_expr)

        # Register proactive_chat jobs from config
        proactive_chats = self._config.get("proactive_chats", []) or []
        for pc in proactive_chats:
            if not pc.get("enabled", True):
                continue
            pc_id = pc.get("id", "")
            schedule = pc.get("schedule", "")
            if not pc_id or not schedule:
                logger.warning("Skipping proactive_chat with missing id/schedule: %s", pc)
                continue

            from .job_store import OpsJob, Trigger, TriggerType, TaskSpec, DeliverySpec
            pc_job = OpsJob(
                job_id=f"proactive_{pc_id}",
                trigger=Trigger(type=TriggerType.CRON, cron_expr=schedule),
                task=TaskSpec(type="proactive_chat"),
                delivery=DeliverySpec(targets=pc.get("targets", [])),
                enabled=True,
            )
            self._jobs[pc_job.job_id] = pc_job
            parts = schedule.split()
            self._apscheduler.add_job(
                self._execute_job, "cron", args=[pc_job.job_id, {"prompt": pc.get("prompt", "")}],
                id=pc_job.job_id, minute=parts[0], hour=parts[1],
            )
            logger.info("Scheduled proactive_chat %s: cron=%s", pc_id, schedule)

        self._apscheduler.start()
        logger.info("OpsScheduler started with %d cron jobs", len(self._apscheduler.get_jobs()))

    def shutdown(self) -> None:
        if self._apscheduler:
            self._apscheduler.shutdown(wait=False)
            logger.info("OpsScheduler shut down")

    def trigger(self, job_id: str, context: dict | None = None) -> None:
        ctx = context or {}
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._execute_job(job_id, ctx))
            else:
                loop.run_until_complete(self._execute_job(job_id, ctx))
        except RuntimeError:
            asyncio.run(self._execute_job(job_id, ctx))

    async def _execute_job(self, job_id: str, context: dict) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            logger.error("Unknown job_id: %s", job_id)
            return

        from .job_store import TriggerType
        trigger_type = TriggerType.CRON if job.trigger.type.value == "cron" else TriggerType.SIGNAL

        run_id = self._job_store.create_run(job_id, trigger_type, context)
        if not run_id:
            return
        if not self._job_store.acquire_run(run_id):
            logger.info("Job %s run %s already acquired, skipping", job_id, run_id)
            return

        from .ops_runner import run_job as execute_task
        result = await execute_task(job, context)

        deliveries_ok = True
        for target_spec in job.delivery.targets:
            from .delivery.base import DeliveryTarget
            target = DeliveryTarget(channel=target_spec["channel"], recipient=target_spec.get("recipient", ""))
            message = result.get("pdf_message") if target.channel == "file" else result.get("message")
            if message is None:
                continue
            delivery_result = await self._router.deliver(target, message)
            from .delivery.result_tracker import record_delivery
            record_delivery(run_id, target.channel, delivery_result)
            if not delivery_result.ok:
                deliveries_ok = False

        self._job_store.complete_run(run_id, ok=result.get("ok", False) and deliveries_ok,
                                     result_data=result.get("result_data", {}), error=result.get("error", ""))
