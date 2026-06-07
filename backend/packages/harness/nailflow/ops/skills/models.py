"""Skill 数据模型 — 对齐 OpenClaw 的 SKILL.md frontmatter 格式。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Skill:
    """一个已解析的技能定义。

    对应 SKILL.md 的 YAML frontmatter + Markdown body。
    """
    name: str
    description: str
    group: str = "nail_ops"
    version: str = "v1"
    tools: list[str] = field(default_factory=list)
    body: str = ""
    file_path: str = ""
    source: str = "builtin"
