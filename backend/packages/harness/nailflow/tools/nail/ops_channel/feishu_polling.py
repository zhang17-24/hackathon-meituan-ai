"""飞书消息轮询监控器 — 替代 WebSocket，通过 API 轮询接收消息并回复。"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 3  # 秒
_MAX_BACKOFF = 30


class FeishuPollingMonitor:
    """轮询飞书消息列表，检测新消息 → Agent 处理 → 回复。"""

    def __init__(self, app_id: str, app_secret: str, *, mention_only: bool = True):
        self._app_id = app_id
        self._app_secret = app_secret
        self._mention_only = mention_only
        self._running = False
        self._last_msg_id: str = ""
        self._bot_name: str = ""
        self._token: str = ""
        self._token_expires: float = 0

    async def _ensure_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires - 60:
            return self._token
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Token failed: {data}")
            self._token = data["tenant_access_token"]
            self._token_expires = time.monotonic() + data.get("expire", 3600)
            return self._token

    async def start(self) -> None:
        self._running = True
        logger.info("FeishuPollingMonitor started (polling every %ds)", _POLL_INTERVAL)
        backoff = 1

        while self._running:
            try:
                await self._poll_once()
                backoff = 1
            except Exception:
                logger.exception("Poll failed, retry in %ds", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF)
                continue

            await asyncio.sleep(_POLL_INTERVAL)

    async def shutdown(self) -> None:
        self._running = False
        logger.info("FeishuPollingMonitor shut down")

    async def _poll_once(self) -> None:
        token = await self._ensure_token()

        # 获取机器人所在的群列表
        async with httpx.AsyncClient(timeout=10) as client:
            chats_resp = await client.get(
                "https://open.feishu.cn/open-apis/im/v1/chats?page_size=10",
                headers={"Authorization": f"Bearer {token}"},
            )
            if chats_resp.status_code != 200:
                return
            chats = chats_resp.json().get("data", {}).get("items", [])
            if not chats:
                return

            # 每个群拉最新消息
            for chat in chats:
                chat_id = chat.get("chat_id", "")
                try:
                    await self._poll_chat(client, token, chat_id)
                except Exception:
                    logger.debug("Poll chat %s failed", chat_id)

    async def _poll_chat(self, client: httpx.AsyncClient, token: str, chat_id: str) -> None:
        resp = await client.get(
            f"https://open.feishu.cn/open-apis/im/v1/messages?container_id_type=chat&container_id={chat_id}&page_size=5&sort_type=ByCreateTimeDesc",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            return

        items = resp.json().get("data", {}).get("items", [])
        if not items:
            return

        # 取最新一条未处理消息
        latest = None
        for item in items:
            if item.get("msg_type") == "text" and item.get("message_id", "") != self._last_msg_id:
                latest = item
                break
        if latest is None:
            return
        msg_id = latest.get("message_id", "")
        self._last_msg_id = msg_id

        msg_type = latest.get("msg_type", "")
        if msg_type != "text":
            return

        # 获取消息内容
        content_str = latest.get("body", {}).get("content", "{}")
        try:
            text = json.loads(content_str).get("text", "")
        except (json.JSONDecodeError, TypeError):
            return

        if not text.strip():
            return

        # mention 过滤
        if self._mention_only:
            at_keywords = ["@机器人", "@ai美甲", "@nailflow", "@运营助手", "@nail"]
            is_mentioned = any(kw in text for kw in at_keywords)
            # 也检查 mentions 结构
            mentions = latest.get("mentions", []) or []
            has_mention = len(mentions) > 0
            if not is_mentioned and not has_mention:
                return

        logger.info("Feishu msg [%s]: %s", chat_id, text[:80])

        # 调用 Agent
        try:
            reply = await self._run_agent(chat_id, text)
            if reply:
                await self._send_reply(client, token, chat_id, reply)
        except Exception:
            logger.exception("Agent run failed")

    async def _run_agent(self, chat_id: str, text: str) -> str:
        """通过 LangGraph API 执行 Agent（与 Web Chat 相同路径，完整 tool calling）。

        使用 stateless /api/runs/stream 端点，通过 config.configurable.thread_id
        传递会话 ID，避免 require_existing 的线程所有权校验。
        """
        from app.gateway.internal_auth import create_internal_auth_headers
        from .feishu_session import get_or_create_thread

        thread_id = get_or_create_thread(chat_id)

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "http://localhost:8001/api/runs/stream",
                json={
                    "input": {
                        "messages": [{"role": "user", "content": text}],
                    },
                    "config": {
                        "configurable": {
                            "thread_id": thread_id,
                            "nail_role": "ops",
                            "nail_page_mode": "ops",
                        },
                    },
                },
                headers=create_internal_auth_headers(),
            )
            resp.raise_for_status()

            accumulated = ""
            async for raw_line in resp.aiter_lines():
                if not raw_line.startswith("data: "):
                    continue
                try:
                    chunk = json.loads(raw_line[6:])
                except json.JSONDecodeError:
                    continue

                if isinstance(chunk.get("data"), list) and len(chunk["data"]) >= 2:
                    msg_type, msg_data = chunk["data"][0], chunk["data"][1]
                    if msg_type in ("ai", "AIMessageChunk"):
                        delta = ""
                        if isinstance(msg_data, dict):
                            delta = msg_data.get("content", "")
                            if isinstance(delta, list):
                                delta = "".join(
                                    d.get("text", "") if isinstance(d, dict) else str(d)
                                    for d in delta
                                )
                            elif not isinstance(delta, str):
                                delta = str(delta)
                        accumulated += delta

        return accumulated.strip()

    async def _send_reply(self, client: httpx.AsyncClient, token: str, chat_id: str, text: str) -> None:
        resp = await client.post(
            f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
            json={
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": text[:29000]}),
            },
        )
        if resp.status_code == 200 and resp.json().get("code") == 0:
            logger.info("Replied to chat %s (%d chars)", chat_id, len(text))
        else:
            logger.error("Reply failed: %s", resp.text[:200])
