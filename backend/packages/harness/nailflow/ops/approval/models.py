"""Approval 审批系统数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"


class ActionType(str, Enum):
    SHELF_ADJUST = "shelf_adjust"
    PRICE_CHANGE = "price_change"
    STYLE_HIDE = "style_hide"
    BATCH_UPLOAD = "batch_upload"


@dataclass
class ApprovalRecord:
    """一条审批记录。"""
    id: str = ""
    proposal_id: str = ""
    action_type: str = ""
    target: str = "{}"           # JSON string: {"style_ids": [...], "from": "...", "to": "..."}
    previous_state: str | None = None  # JSON string: 回滚快照
    status: str = "pending"
    operator: str = ""
    reject_reason: str = ""
    rollback_reason: str = ""
    created_at: str = ""
    resolved_at: str = ""
    rollback_at: str = ""


# 低风险操作：自动执行，仅记录日志
LOW_RISK_ACTIONS = {
    "ranking_adjust",    # 推荐位排序调整
    "label_update",      # 标签更新
    "data_report",       # 数据报表
}

# 高风险操作：必须人工 approve
HIGH_RISK_ACTIONS = {
    "shelf_adjust",      # 款式上下架
    "price_change",      # 价格调整
    "style_hide",        # 款式隐藏
    "batch_upload",      # 批量上架
}
