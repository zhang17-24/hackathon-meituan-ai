"""钉钉通道适配器：webhook 模式，支持 Markdown + 卡片转 Markdown。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import quote_plus

import httpx

from ..base import AbstractChannelAdapter, ChannelCapability, DeliveryResult, DeliveryTarget

if TYPE_CHECKING:
    from ..messages.base import AbstractMessage

logger = logging.getLogger(__name__)


class DingTalkAdapter(AbstractChannelAdapter):
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self._webhook_url = cfg.get("webhook_url", "")
        self._secret = cfg.get("secret", "")
        self._timeout = cfg.get("timeout", 10)

    @property
    def channel_id(self) -> str:
        return "dingtalk"

    @property
    def capabilities(self) -> ChannelCapability:
        return ChannelCapability.TEXT | ChannelCapability.MARKDOWN

    async def send(self, target: DeliveryTarget, message: "AbstractMessage") -> DeliveryResult:
        webhook_url = target.recipient or self._webhook_url
        if not webhook_url:
            return DeliveryResult(ok=False, channel="dingtalk", error="No webhook URL configured")
        try:
            signed_url = self._sign_url(webhook_url)
            payload = self._build_payload(message)
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(signed_url, json=payload,
                                         headers={"Content-Type": "application/json"})
                resp.raise_for_status()
                data = resp.json()
                return DeliveryResult(ok=data.get("errcode") == 0, channel="dingtalk",
                                      message_id=str(data.get("msgid", "")),
                                      error=data.get("errmsg", ""))
        except Exception as e:
            logger.error("DingTalk send failed: %s", e)
            return DeliveryResult(ok=False, channel="dingtalk", error=str(e))

    def _sign_url(self, url: str) -> str:
        if not self._secret:
            return url
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = quote_plus(base64.b64encode(hmac_code).decode())
        return f"{url}&timestamp={timestamp}&sign={sign}"

    def _build_payload(self, message: "AbstractMessage") -> dict[str, Any]:
        from ..messages.base import CardMessage, MarkdownMessage, TextMessage
        if isinstance(message, MarkdownMessage):
            return {
                "msgtype": "markdown",
                "markdown": {"title": getattr(message, "title", "nailflow"), "text": message.content},
            }
        elif isinstance(message, CardMessage):
            lines = [f"### {message.header_title}"]
            for section in message.sections:
                if section.title:
                    lines.append(f"**{section.title}**")
                lines.extend(section.lines)
            return {"msgtype": "markdown", "markdown": {"title": message.header_title, "text": "\n\n".join(lines)}}
        else:
            content = message.content if isinstance(message, TextMessage) else str(message)
            return {"msgtype": "text", "text": {"content": content}}
