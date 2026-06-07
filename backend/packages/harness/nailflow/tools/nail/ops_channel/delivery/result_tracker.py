# ops_channel/delivery/result_tracker.py
"""投递结果追踪：记录到 ops_job_runs.result JSON 字段。"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import DeliveryResult

logger = logging.getLogger(__name__)


def record_delivery(run_id: str, channel: str, result: "DeliveryResult") -> None:
    try:
        from ...base import get_db
        with get_db() as conn:
            row = conn.execute("SELECT result FROM ops_job_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return
            existing = {}
            if row["result"]:
                try:
                    existing = json.loads(row["result"])
                except json.JSONDecodeError:
                    pass
            deliveries = existing.get("deliveries", {})
            deliveries[channel] = {"ok": result.ok, "message_id": result.message_id, "error": result.error}
            existing["deliveries"] = deliveries
            conn.execute("UPDATE ops_job_runs SET result = ? WHERE id = ?",
                         (json.dumps(existing, ensure_ascii=False), run_id))
            conn.commit()
    except Exception:
        logger.exception("record_delivery failed for run %s channel %s", run_id, channel)
