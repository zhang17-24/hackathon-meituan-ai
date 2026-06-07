# ops_channel/feishu_reply.py
"""飞书 Open API 消息发送 — 使用 tenant_access_token 回复/发送消息。"""
from __future__ import annotations

import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

_MAX_TEXT_LEN = 29000  # 飞书单条消息限 30KB，留 buffer


class FeishuReplySender:
    """通过飞书 Open API 发送/回复消息。"""

    def __init__(self, app_id: str, app_secret: str):
        self._app_id = app_id
        self._app_secret = app_secret
        self._token: str = ""
        self._token_expires_at: float = 0

    async def _ensure_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at - 60:
            return self._token
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["tenant_access_token"]
            self._token_expires_at = time.monotonic() + data.get("expire", 7200)
            logger.debug("Feishu token refreshed, expires in %ds", data.get("expire", 7200))
        return self._token

    async def reply(self, root_msg_id: str, text: str) -> bool:
        """回复飞书消息（在消息线程中回复）。"""
        token = await self._ensure_token()
        for chunk in _split_long_text(text):
            ok = await self._send_message(token, "reply", root_msg_id, chunk)
            if not ok:
                return False
        return True

    async def send_to_chat(self, chat_id: str, text: str) -> bool:
        """向指定飞书群/用户发送新消息。"""
        token = await self._ensure_token()
        for chunk in _split_long_text(text):
            ok = await self._send_to_chat_id(token, chat_id, chunk)
            if not ok:
                return False
        return True

    async def _send_message(self, token: str, msg_type: str, root_id: str, text: str) -> bool:
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{root_id}/reply"
        body = {
            "content": json.dumps({"text": text}),
            "msg_type": "text",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url, json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                return True
            logger.error("Feishu reply failed: status=%d body=%s", resp.status_code, resp.text)
            return False

    async def _send_to_chat_id(self, token: str, chat_id: str, text: str) -> bool:
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": "chat_id"}
        body = {
            "receive_id": chat_id,
            "content": json.dumps({"text": text}),
            "msg_type": "text",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url, json=body, params=params,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                return True
            logger.error("Feishu send failed: status=%d body=%s", resp.status_code, resp.text)
            return False


def _split_long_text(text: str) -> list[str]:
    if len(text.encode("utf-8")) <= _MAX_TEXT_LEN:
        return [text] if text.strip() else []
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        test = current + ("\n" if current else "") + line
        if len(test.encode("utf-8")) > _MAX_TEXT_LEN:
            if current:
                chunks.append(current)
            current = line
        else:
            current = test
    if current:
        chunks.append(current)
    return chunks
