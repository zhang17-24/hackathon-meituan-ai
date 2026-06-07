# ops_channel/delivery/adapters/web_push.py
"""Web 看板推送适配器：内存队列 → WebSocket/HTTP 拉取。"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import TYPE_CHECKING, Any

from ..base import AbstractChannelAdapter, ChannelCapability, DeliveryResult, DeliveryTarget

if TYPE_CHECKING:
    from ..messages.base import AbstractMessage

logger = logging.getLogger(__name__)

_MAX_MESSAGES = 100
_inbox: deque[dict[str, Any]] = deque(maxlen=_MAX_MESSAGES)


def get_recent_messages(since_ts: float = 0) -> list[dict[str, Any]]:
    result = []
    for msg in _inbox:
        if msg["ts"] > since_ts:
            result.append(msg)
    return result


class WebPushAdapter(AbstractChannelAdapter):
    def __init__(self, config: dict | None = None):
        pass

    @property
    def channel_id(self) -> str:
        return "web_push"

    @property
    def capabilities(self) -> ChannelCapability:
        return ChannelCapability.TEXT | ChannelCapability.CARD | ChannelCapability.BUTTON | ChannelCapability.MARKDOWN

    async def send(self, target: DeliveryTarget, message: "AbstractMessage") -> DeliveryResult:
        try:
            entry = {"ts": time.time(), "kind": message.kind.value, "payload": message.to_primitive()}
            _inbox.append(entry)
            return DeliveryResult(ok=True, channel="web_push", message_id=str(entry["ts"]))
        except Exception as e:
            return DeliveryResult(ok=False, channel="web_push", error=str(e))
