"""Memory 记忆系统数据模型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MemoryType(str, Enum):
    TREND = "trend"
    MARKETING = "marketing"
    RISK = "risk"
    FEEDBACK = "feedback"


@dataclass
class MemoryEntry:
    """一条运营记忆。"""
    id: int = 0
    memory_type: str = "marketing"
    content: str = ""
    created_at: str = ""
    source: str = ""  # agent / manual
    run_id: str = ""
