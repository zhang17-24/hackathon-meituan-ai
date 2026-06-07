# ops_channel/delivery/adapters/feishu.py
"""飞书通道适配器：webhook 模式，支持卡片 + 文本。"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import httpx

from ..base import AbstractChannelAdapter, ChannelCapability, DeliveryResult, DeliveryTarget

if TYPE_CHECKING:
    from ..messages.base import AbstractMessage

logger = logging.getLogger(__name__)

_FEISHU_COLORS = {"blue": "blue", "pink": "pink", "green": "green", "red": "red", "purple": "purple"}


class FeishuAdapter(AbstractChannelAdapter):
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self._webhook_url = cfg.get("webhook_url", "")
        self._timeout = cfg.get("timeout", 10)

    @property
    def channel_id(self) -> str:
        return "feishu"

    @property
    def capabilities(self) -> ChannelCapability:
        return ChannelCapability.TEXT | ChannelCapability.CARD | ChannelCapability.BUTTON | ChannelCapability.MARKDOWN

    async def send(self, target: DeliveryTarget, message: "AbstractMessage") -> DeliveryResult:
        webhook_url = target.recipient or self._webhook_url
        if not webhook_url:
            return DeliveryResult(ok=False, channel="feishu", error="No webhook URL configured")
        try:
            payload = self._build_payload(message)
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
                resp.raise_for_status()
                data = resp.json()
                msg_id = data.get("data", {}).get("message_id", "")
                return DeliveryResult(ok=True, channel="feishu", message_id=msg_id)
        except Exception as e:
            logger.error("Feishu send failed: %s", e)
            return DeliveryResult(ok=False, channel="feishu", error=str(e))

    def _build_payload(self, message: "AbstractMessage") -> dict[str, Any]:
        from ..messages.base import CardMessage, MarkdownMessage, TextMessage
        if isinstance(message, CardMessage):
            return self._build_card(message)
        elif isinstance(message, MarkdownMessage):
            return {"msg_type": "text", "content": {"text": message.content}}
        else:
            content = message.content if isinstance(message, TextMessage) else message.to_primitive().get("content", "")
            return {"msg_type": "text", "content": {"text": content}}

    def _build_card(self, card: "CardMessage") -> dict[str, Any]:
        from ..messages.base import CardMessage as CM
        elements: list[dict] = []
        elements.append({"tag": "markdown", "content": f"**{card.header_title}**"})
        for section in card.sections:
            if section.title:
                elements.append({"tag": "markdown", "content": f"**{section.title}**"})
            for line_text in section.lines:
                elements.append({"tag": "markdown", "content": line_text})
            for label, value in section.highlight_fields.items():
                elements.append({"tag": "markdown", "content": f"{label}: **{value}**"})
        if card.buttons:
            actions: list[dict] = []
            for btn in card.buttons:
                btn_type = "primary" if btn.style == "primary" else ("danger" if btn.style == "danger" else "default")
                actions.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": btn.label},
                    "type": btn_type,
                    "value": json.dumps({"action": btn.action, "value": btn.value}),
                })
            elements.append({"tag": "action", "actions": actions})
        header_color = _FEISHU_COLORS.get(card.header_color, "blue")
        return {
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": card.header_title}, "template": header_color},
                "elements": elements,
            },
        }
