# ops_channel/job_store.py
"""Job 定义与 run 记录持久化。"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    CRON = "cron"
    INTERVAL = "interval"
    SIGNAL = "signal"
    MANUAL = "manual"


@dataclass
class DeliverySpec:
    targets: list[dict] = field(default_factory=list)


@dataclass
class TaskSpec:
    type: str = ""


@dataclass
class Trigger:
    type: TriggerType
    cron_expr: str = ""
    signal_threshold: float = 3.0


@dataclass
class OpsJob:
    job_id: str
    trigger: Trigger
    task: TaskSpec
    delivery: DeliverySpec
    enabled: bool = True


def create_run(job_id: str, trigger_type: TriggerType, payload: dict | None = None) -> str:
    from ..base import get_db
    run_id = str(uuid.uuid4())
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO ops_job_runs (id, job_id, status, trigger_type, payload) VALUES (?,?,?,?,?)",
                (run_id, job_id, "queued", trigger_type.value, json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()
        return run_id
    except Exception:
        logger.exception("create_run failed for job %s", job_id)
        return ""


def acquire_run(run_id: str) -> bool:
    from ..base import get_db
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "UPDATE ops_job_runs SET status='running' WHERE id=? AND status='queued'", (run_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        logger.exception("acquire_run failed for %s", run_id)
        return False


def complete_run(run_id: str, ok: bool, result_data: dict | None = None, error: str = "") -> None:
    from ..base import get_db
    status = "delivered" if ok else "failed"
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE ops_job_runs SET status=?, result=?, error=?, completed_at=datetime('now') WHERE id=?",
                (status, json.dumps(result_data or {}, ensure_ascii=False), error, run_id),
            )
            conn.commit()
    except Exception:
        logger.exception("complete_run failed for %s", run_id)


def get_baseline_signal_count(style_id: str, days: int = 7) -> float:
    from ..base import get_db
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM ops_signals WHERE style_id=? AND created_at>=datetime('now',?)",
                (style_id, f"-{days} days"),
            ).fetchone()
        count = row["cnt"] if row else 0
        return max(count / days, 1.0)
    except Exception:
        return 1.0
