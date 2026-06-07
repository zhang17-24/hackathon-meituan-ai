# ops_channel/delivery/router.py
"""通道路由器：按能力自动降级路由。"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import DeliveryResult, DeliveryTarget
    from .messages.base import AbstractMessage, CardMessage, MarkdownMessage
    from .registry import AdapterRegistry

logger = logging.getLogger(__name__)


class ChannelRouter:
    def __init__(self, registry: "AdapterRegistry"):
        self._registry = registry

    async def deliver(self, target: "DeliveryTarget", message: "AbstractMessage") -> "DeliveryResult":
        from .base import DeliveryResult

        adapter = self._registry.get(target.channel)
        if adapter is None:
            return DeliveryResult(ok=False, channel=target.channel,
                                  error=f"No adapter for channel '{target.channel}'")
        degraded = self._auto_degrade(adapter.capabilities, message)
        return await adapter.send(target, degraded)

    def _auto_degrade(self, caps: "ChannelCapability", msg: "AbstractMessage") -> "AbstractMessage":
        from .base import ChannelCapability as CC
        from .messages.base import CardMessage, MarkdownMessage, TextMessage

        if isinstance(msg, CardMessage):
            if CC.CARD in caps:
                return msg
            md = self._card_to_markdown(msg)
            if CC.MARKDOWN in caps:
                return md
            return TextMessage(content=md.content)

        if isinstance(msg, MarkdownMessage):
            if CC.MARKDOWN in caps:
                return msg
            return TextMessage(content=msg.content)

        return msg

    def _card_to_markdown(self, card: "CardMessage") -> "MarkdownMessage":
        from .messages.base import MarkdownMessage
        lines = [f"**{card.header_title}**", ""]
        for s in card.sections:
            if s.title:
                lines.append(f"**{s.title}**")
            for lt in s.lines:
                lines.append(f"- {lt}")
            for label, value in s.highlight_fields.items():
                lines.append(f"- {label}: **{value}**")
            lines.append("")
        if card.buttons:
            labels = [b.label for b in card.buttons]
            lines.append(" | ".join(labels))
        return MarkdownMessage(content="\n".join(lines))
