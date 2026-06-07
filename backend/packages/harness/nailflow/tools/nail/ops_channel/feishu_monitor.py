# ops_channel/feishu_monitor.py
"""飞书 WebSocket 长连接 — 接收消息事件，路由到 LangGraph Agent 并回复。"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEBOUNCE_MS = 0.5
_MAX_BACKOFF = 60


class FeishuMonitor:
    """飞书 WebSocket 长连接监控器。

    启动后建立到飞书开放平台的 WS 连接，接收 im.message.receive_v1 事件，
    路由到 LangGraph Agent 执行，完成后回复到飞书。
    """

    def __init__(self, app_id: str, app_secret: str, *, mention_only: bool = True):
        self._app_id = app_id
        self._app_secret = app_secret
        self._mention_only = mention_only
        self._ws: Any = None
        self._running = False
        self._recent_msg_ids: dict[str, float] = {}
        self._reply_sender: Any = None

    async def start(self) -> None:
        from .feishu_reply import FeishuReplySender

        self._reply_sender = FeishuReplySender(self._app_id, self._app_secret)
        self._running = True
        backoff = 1
        while self._running:
            try:
                await self._connect_and_listen()
                backoff = 1
            except Exception:
                logger.exception("Feishu WS connection lost, reconnecting in %ds...", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF)

    async def shutdown(self) -> None:
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.aclose()
            except Exception:
                pass
            self._ws = None

    async def _connect_and_listen(self) -> None:
        import websockets

        token = await self._reply_sender._ensure_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://open.feishu.cn/open-apis/ws/v1/connection",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            conn_info = resp.json()
        ws_url = conn_info["data"]["url"]
        ws_token = conn_info["data"]["token"]
        logger.info("Feishu WS connecting to %s...", ws_url[:60])

        self._ws = await websockets.connect(
            ws_url,
            additional_headers={"Authorization": f"Bearer {ws_token}"},
            ping_interval=30,
            ping_timeout=10,
        )

        async for raw in self._ws:
            if not self._running:
                break
            try:
                event = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                continue
            await self._handle_event(event)

    async def _handle_event(self, event: dict) -> None:
        event_type = event.get("type", "")
        if event_type != "im.message.receive_v1":
            return

        data = event.get("data", {}) or {}
        msg_data = data.get("message", {}) or {}
        msg_id = msg_data.get("message_id", "")
        chat_id = msg_data.get("chat_id", "")

        # 去重
        now = time.monotonic()
        if msg_id and msg_id in self._recent_msg_ids:
            if now - self._recent_msg_ids[msg_id] < _DEBOUNCE_MS:
                return
        if msg_id:
            self._recent_msg_ids[msg_id] = now
        self._recent_msg_ids = {k: v for k, v in self._recent_msg_ids.items() if now - v < 10}

        chat_type = msg_data.get("chat_type", "group")

        # 群聊 @机器人 过滤
        if self._mention_only and chat_type == "group":
            mentions = msg_data.get("mentions", []) or []
            if not mentions:
                return

        # 提取文本内容
        content_str = msg_data.get("content", "{}")
        try:
            content_obj = json.loads(content_str)
            text = content_obj.get("text", "")
        except (json.JSONDecodeError, TypeError):
            text = str(content_str)

        if not text.strip():
            return

        sender = data.get("sender", {}) or {}
        sender_id = sender.get("sender_id", {}) or {}
        open_id = sender_id.get("open_id", "")

        logger.info("Feishu message: chat=%s open_id=%s text=%s", chat_id, open_id, text[:80])

        try:
            reply_text = await self._run_agent(chat_id, chat_type, text, open_id)
            if reply_text:
                await self._reply_sender.reply(msg_id, reply_text)
                logger.info("Replied to msg_id=%s chat=%s", msg_id, chat_id)
        except Exception:
            logger.exception("Agent run failed for chat=%s", chat_id)
            try:
                await self._reply_sender.reply(msg_id, "抱歉，处理您的请求时出现了错误，请稍后重试。")
            except Exception:
                pass

    async def _run_agent(self, chat_id: str, chat_type: str, text: str, open_id: str) -> str:
        from app.gateway.internal_auth import create_internal_auth_headers
        from .feishu_session import get_or_create_thread

        thread_id = get_or_create_thread(chat_id, chat_type)

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
