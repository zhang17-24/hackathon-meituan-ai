"""ApprovalManager — 审批状态机 + 回滚 + 超时自动过期。"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .models import LOW_RISK_ACTIONS, ApprovalRecord, ApprovalStatus

logger = logging.getLogger(__name__)

_EXPIRE_HOURS = 24


class ApprovalManager:
    """管理运营方案审批生命周期。"""

    def propose(self, action_type: str, target: dict, payload: dict | None = None,
                risk: str = "high") -> str:
        """创建提案。低风险自动 approved，高风险 pending。

        Returns:
            proposal_id 字符串。
        """
        proposal_id = str(uuid.uuid4())
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        is_low_risk = action_type in LOW_RISK_ACTIONS or risk == "low"

        initial_status = ApprovalStatus.APPROVED if is_low_risk else ApprovalStatus.PENDING
        resolved = now if is_low_risk else None

        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO approval_records
                       (id, proposal_id, action_type, target, status, created_at, resolved_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (record_id, proposal_id, action_type,
                     json.dumps(target, ensure_ascii=False),
                     initial_status.value, now, resolved),
                )
                conn.commit()
        except Exception as e:
            logger.error("ApprovalManager.propose failed: %s", e)
            raise

        if is_low_risk:
            logger.info("Low-risk action %s auto-approved: %s", action_type, proposal_id)
        else:
            logger.info("High-risk action %s pending approval: %s", action_type, proposal_id)

        return proposal_id

    def approve(self, proposal_id: str, operator: str) -> bool:
        """批准提案，状态 → approved → executed。"""
        record = self._get_by_proposal(proposal_id)
        if record is None:
            return False
        if record.status != ApprovalStatus.PENDING.value:
            logger.warning("Cannot approve proposal %s in status %s", proposal_id, record.status)
            return False

        now = datetime.now(timezone.utc).isoformat()
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                conn.execute(
                    """UPDATE approval_records
                       SET status = ?, operator = ?, resolved_at = ?
                       WHERE proposal_id = ? AND status = ?""",
                    (ApprovalStatus.EXECUTED.value, operator, now, proposal_id, ApprovalStatus.PENDING.value),
                )
                # 同步更新 action_proposals 表
                conn.execute(
                    "UPDATE action_proposals SET status = ?, confirmed_at = ? WHERE id = ?",
                    ("approved", now, proposal_id),
                )
                conn.commit()
        except Exception as e:
            logger.error("ApprovalManager.approve failed: %s", e)
            return False

        logger.info("Proposal %s approved+executed by %s", proposal_id, operator)
        return True

    def reject(self, proposal_id: str, operator: str, reason: str = "") -> bool:
        """拒绝提案。"""
        record = self._get_by_proposal(proposal_id)
        if record is None:
            return False
        if record.status != ApprovalStatus.PENDING.value:
            return False

        now = datetime.now(timezone.utc).isoformat()
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                conn.execute(
                    """UPDATE approval_records
                       SET status = ?, operator = ?, reject_reason = ?, resolved_at = ?
                       WHERE proposal_id = ? AND status = ?""",
                    (ApprovalStatus.REJECTED.value, operator, reason, now, proposal_id, ApprovalStatus.PENDING.value),
                )
                conn.execute(
                    "UPDATE action_proposals SET status = ?, confirmed_at = ? WHERE id = ?",
                    ("rejected", now, proposal_id),
                )
                conn.commit()
        except Exception as e:
            logger.error("ApprovalManager.reject failed: %s", e)
            return False

        logger.info("Proposal %s rejected by %s: %s", proposal_id, operator, reason)
        return True

    def rollback(self, proposal_id: str, operator: str, reason: str = "") -> bool:
        """回滚已执行的操作，通过 previous_state 恢复原状态。"""
        record = self._get_by_proposal(proposal_id)
        if record is None:
            return False
        if record.status != ApprovalStatus.EXECUTED.value:
            logger.warning("Cannot rollback proposal %s in status %s", proposal_id, record.status)
            return False

        now = datetime.now(timezone.utc).isoformat()
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                conn.execute(
                    """UPDATE approval_records
                       SET status = ?, operator = ?, rollback_reason = ?, rollback_at = ?
                       WHERE proposal_id = ? AND status = ?""",
                    (ApprovalStatus.ROLLED_BACK.value, operator, reason, now, proposal_id, ApprovalStatus.EXECUTED.value),
                )
                conn.commit()
        except Exception as e:
            logger.error("ApprovalManager.rollback failed: %s", e)
            return False

        logger.info("Proposal %s rolled back by %s: %s", proposal_id, operator, reason)
        return True

    def auto_expire(self) -> int:
        """超时 24h 的 pending 提案自动过期。返回过期数量。"""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=_EXPIRE_HOURS)).isoformat()
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                cursor = conn.execute(
                    """UPDATE approval_records
                       SET status = ?
                       WHERE status = ? AND created_at < ?""",
                    (ApprovalStatus.EXPIRED.value, ApprovalStatus.PENDING.value, cutoff),
                )
                conn.commit()
                count = cursor.rowcount
        except Exception as e:
            logger.error("ApprovalManager.auto_expire failed: %s", e)
            return 0

        if count:
            logger.info("Auto-expired %d pending proposals", count)
        return count

    def list_pending(self, limit: int = 20) -> list[dict[str, Any]]:
        """列出待审批记录。"""
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                rows = conn.execute(
                    """SELECT * FROM approval_records
                       WHERE status = ? ORDER BY created_at DESC LIMIT ?""",
                    (ApprovalStatus.PENDING.value, limit),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error("ApprovalManager.list_pending failed: %s", e)
            return []

    def set_previous_state(self, proposal_id: str, state: dict) -> bool:
        """在执行前保存 previous_state 快照，用于回滚。"""
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                conn.execute(
                    "UPDATE approval_records SET previous_state = ? WHERE proposal_id = ?",
                    (json.dumps(state, ensure_ascii=False), proposal_id),
                )
                conn.commit()
        except Exception as e:
            logger.error("ApprovalManager.set_previous_state failed: %s", e)
            return False
        return True

    def _get_by_proposal(self, proposal_id: str) -> ApprovalRecord | None:
        try:
            from nailflow.tools.nail.base import get_db
            with get_db() as conn:
                row = conn.execute(
                    "SELECT * FROM approval_records WHERE proposal_id = ?", (proposal_id,)
                ).fetchone()
                if row is None:
                    return None
                d = dict(row)
                return ApprovalRecord(
                    id=d.get("id", ""),
                    proposal_id=d.get("proposal_id", ""),
                    action_type=d.get("action_type", ""),
                    target=d.get("target", "{}"),
                    previous_state=d.get("previous_state"),
                    status=d.get("status", "pending"),
                    operator=d.get("operator", ""),
                    reject_reason=d.get("reject_reason", ""),
                    rollback_reason=d.get("rollback_reason", ""),
                    created_at=d.get("created_at", ""),
                    resolved_at=d.get("resolved_at", ""),
                    rollback_at=d.get("rollback_at", ""),
                )
        except Exception as e:
            logger.error("ApprovalManager._get_by_proposal failed: %s", e)
            return None
