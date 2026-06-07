# ops_channel/delivery/messages/card.py
"""卡片构建组件：CardSection / CardButton。"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CardSection:
    title: str = ""
    lines: list[str] = field(default_factory=list)
    highlight_fields: dict[str, str] = field(default_factory=dict)

    def to_primitive(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.title:
            result["title"] = self.title
        if self.lines:
            result["lines"] = self.lines
        if self.highlight_fields:
            result["highlight_fields"] = self.highlight_fields
        return result


@dataclass
class CardButton:
    label: str
    action: str
    value: str = ""
    style: str = "default"

    def to_primitive(self) -> dict[str, Any]:
        return {"label": self.label, "action": self.action, "value": self.value, "style": self.style}
