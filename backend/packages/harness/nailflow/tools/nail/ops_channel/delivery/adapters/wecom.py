"""企业微信通道适配器：群机器人 Webhook 模式，支持 Markdown + 文本 + 图文消息。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from ..base import AbstractChannelAdapter, ChannelCapability, DeliveryResult, DeliveryTarget

if TYPE_CHECKING:
    from ..messages.base import AbstractMessage

logger = logging.getLogger(__name__)


class WeComAdapter(AbstractChannelAdapter):
    """企业微信群机器人 Webhook 适配器。

    环境变量：WECOM_WEBHOOK_URL
    文档：https://developer.work.weixin.qq.com/document/path/91770
    """

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self._webhook_url = cfg.get("webhook_url", "")
        self._timeout = cfg.get("timeout", 10)

    @property
    def channel_id(self) -> str:
        return "wecom"

    @property
    def capabilities(self) -> ChannelCapability:
        return (ChannelCapability.TEXT | ChannelCapability.MARKDOWN
                | ChannelCapability.CARD)

    async def send(self, target: DeliveryTarget, message: "AbstractMessage") -> DeliveryResult:
        webhook_url = target.recipient or self._webhook_url
        if not webhook_url:
            return DeliveryResult(ok=False, channel="wecom", error="No webhook URL configured")
        try:
            payload = self._build_payload(message)
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(webhook_url, json=payload,
                                         headers={"Content-Type": "application/json"})
                resp.raise_for_status()
                data = resp.json()
                return DeliveryResult(ok=data.get("errcode") == 0, channel="wecom",
                                      message_id="", error=data.get("errmsg", ""))
        except Exception as e:
            logger.error("WeCom send failed: %s", e)
            return DeliveryResult(ok=False, channel="wecom", error=str(e))

    def _build_payload(self, message: "AbstractMessage") -> dict[str, Any]:
        from ..messages.base import CardMessage, MarkdownMessage, TextMessage

        if isinstance(message, CardMessage):
            return self._build_card(message)
        elif isinstance(message, MarkdownMessage):
            return {
                "msgtype": "markdown",
                "markdown": {"content": message.content},
            }
        else:
            content = message.content if isinstance(message, TextMessage) else str(message)
            return {"msgtype": "text", "text": {"content": content}}

    def _build_card(self, card: "CardMessage") -> dict[str, Any]:
        """CardMessage → 企业微信图文消息。

        企业微信不支持飞书式交互卡片，转为 markdown 格式的消息。
        按钮转为带链接的文本行。
        """
        lines = [f"## {card.header_title}", ""]
        for section in card.sections:
            if section.title:
                lines.append(f"**{section.title}**")
            for line_text in section.lines:
                lines.append(f"> {line_text}")
            for label, value in section.highlight_fields.items():
                lines.append(f"> {label}: **{value}**")
            lines.append("")

        if card.buttons:
            lines.append("---")
            for btn in card.buttons:
                emoji = {"primary": "", "danger": "⚠️ ", "default": ""}.get(btn.style, "")
                lines.append(f"{emoji}{btn.label}")

        return {
            "msgtype": "markdown",
            "markdown": {"content": "\n".join(lines)},
        }
