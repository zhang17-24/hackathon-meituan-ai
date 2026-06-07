# ops_channel/feishu_session.py
"""飞书会话映射 — chat_id ↔ LangGraph Thread ID 持久化。"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, UTC

import httpx

from app.gateway.internal_auth import create_internal_auth_headers

logger = logging.getLogger(__name__)


def get_or_create_thread(chat_id: str, chat_type: str = "group") -> str:
    """查找已有 thread_id，不存在则通过 Gateway API 创建并持久化。"""
    from ..base import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT thread_id FROM feishu_sessions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE feishu_sessions SET last_active = ? WHERE chat_id = ?",
                (datetime.now(UTC).isoformat(), chat_id),
            )
            return row["thread_id"]

    thread_id = _create_thread_sync()
    if not thread_id:
        raise RuntimeError(f"Failed to create LangGraph thread for chat_id={chat_id}")

    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO feishu_sessions(chat_id, thread_id, chat_type, created_at, last_active) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, thread_id, chat_type, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()),
        )
    logger.info("Created session: chat_id=%s -> thread_id=%s", chat_id, thread_id)
    return thread_id


def _create_thread_sync() -> str:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(_async_create(), loop)
            return future.result(timeout=10)
        return loop.run_until_complete(_async_create())
    except RuntimeError:
        return asyncio.run(_async_create())


async def _async_create() -> str:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "http://localhost:8001/api/threads",
            headers=create_internal_auth_headers(),
            json={},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("thread_id") or data.get("id", "")


def get_thread_id(chat_id: str) -> str | None:
    """仅查找，不创建。"""
    from ..base import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT thread_id FROM feishu_sessions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return row["thread_id"] if row else None
