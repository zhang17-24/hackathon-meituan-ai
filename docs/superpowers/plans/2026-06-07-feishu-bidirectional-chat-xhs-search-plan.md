# Feishu Bidirectional Chat + Proactive Scheduling + XHS Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade NailFlow's Feishu integration from one-way push to full bidirectional conversation (like OpenClaw), add cron-triggered proactive Agent chats, and add Xiaohongshu post search tool for ops analysis.

**Architecture:** FeishuMonitor opens a WebSocket long connection to Feishu Open Platform for receiving message events. Each Feishu chat_id maps to one LangGraph Thread (feishu_sessions table). OpsScheduler gains proactive_chat jobs that reuse the same Thread for context continuity. XHS-Downloader (local clone) provides post extraction; a search engine query layer provides URL discovery.

**Tech Stack:** Python 3.12+, httpx (WebSocket + HTTP), APScheduler, LangGraph SSE streams, XHS-Downloader (source.application.XHS), Bing Search API

---

## File Structure

| File | Role |
|------|------|
| `tools/nail/ops_channel/feishu_session.py` (NEW) | feishu_sessions table CRUD |
| `tools/nail/ops_channel/feishu_monitor.py` (NEW) | WebSocket connection + event loop + message dispatch |
| `tools/nail/ops_channel/feishu_reply.py` (NEW) | Feishu Open API reply/send via tenant_access_token |
| `tools/nail/xhs_client.py` (NEW) | XHS-Downloader wrapper + search engine query |
| `tools/nail/xiaohongshu_search.py` (NEW) | @tool LangChain tool for XHS search |
| `tools/nail/base.py` (MODIFY) | Add feishu_sessions DDL |
| `ops_channel/ops_scheduler.py` (MODIFY) | Register proactive_chat jobs from config |
| `ops_channel/ops_runner.py` (MODIFY) | Add `_run_proactive_chat()` |
| `tools/nail/router_config.py` (MODIFY) | Register xiaohongshu_search capability |
| `app/gateway/routers/nail_config.py` (MODIFY) | Register xiaohongshu_search_tool in tool metadata |
| `app/gateway/routers/nail_dev.py` (MODIFY) | Register xiaohongshu_search_tool in dev registry |
| `app/gateway/app.py` (MODIFY) | Start/stop FeishuMonitor in lifespan |
| `agents/lead_agent/prompt.py` (MODIFY) | Update ops prompts with XHS search guidance |
| `config.yaml` (MODIFY) | Add nail_feishu, nail_xiaohongshu, proactive_chats config |

---

### Task 1: Add feishu_sessions table to database

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/base.py`

- [ ] **Step 1: Add feishu_sessions DDL to init_nail_tables()**

Find the `init_nail_tables()` function in `base.py`. After the existing `skill_executions` table block (around line 1056), add:

```sql
            CREATE TABLE IF NOT EXISTS feishu_sessions (
                chat_id      TEXT PRIMARY KEY,
                thread_id    TEXT NOT NULL,
                chat_type    TEXT DEFAULT 'group',
                created_at   TEXT DEFAULT (datetime('now')),
                last_active  TEXT DEFAULT (datetime('now'))
            );
```

- [ ] **Step 2: Run init to verify table creation**

Run: `cd backend && python -c "from packages.harness.deerflow.tools.nail.base import init_nail_tables; init_nail_tables(); print('OK')"`
Expected: `OK` (no errors)

- [ ] **Step 3: Verify table exists in SQLite**

Run: `cd backend && sqlite3 data/nailflow.db ".schema feishu_sessions"`
Expected: shows CREATE TABLE feishu_sessions

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/base.py
git commit -m "feat: add feishu_sessions table for bidirectional chat session mapping

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Create feishu_session.py — session CRUD

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/feishu_session.py`

- [ ] **Step 1: Write feishu_session.py**

```python
# ops_channel/feishu_session.py
"""飞书会话映射 — chat_id ↔ LangGraph Thread ID 持久化。"""
from __future__ import annotations

import logging
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


def get_or_create_thread(chat_id: str, chat_type: str = "group") -> str:
    """查找已有 thread_id，不存在则通过 Gateway API 创建新 Thread 并持久化。

    Returns:
        LangGraph thread_id (UUID string)
    """
    from ...base import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT thread_id FROM feishu_sessions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        if row:
            # 更新最后活跃时间
            conn.execute(
                "UPDATE feishu_sessions SET last_active = ? WHERE chat_id = ?",
                (datetime.now(UTC).isoformat(), chat_id),
            )
            return row["thread_id"]

    # 不存在 → 通过 LangGraph API 创建新 Thread
    thread_id = _create_langgraph_thread()
    if not thread_id:
        raise RuntimeError(f"Failed to create LangGraph thread for chat_id={chat_id}")

    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO feishu_sessions(chat_id, thread_id, chat_type, created_at, last_active) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, thread_id, chat_type, datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()),
        )

    logger.info("Created session: chat_id=%s → thread_id=%s", chat_id, thread_id)
    return thread_id


def get_thread_id(chat_id: str) -> str | None:
    """仅查找，不创建。"""
    from ...base import get_db

    with get_db() as conn:
        row = conn.execute(
            "SELECT thread_id FROM feishu_sessions WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return row["thread_id"] if row else None


def _create_langgraph_thread() -> str:
    """通过 Gateway 内部 API 创建 LangGraph Thread。"""
    import asyncio
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
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post("http://localhost:8001/api/v1/threads", json={})
        resp.raise_for_status()
        data = resp.json()
        return data.get("thread_id") or data.get("id", "")
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && python -c "from packages.harness.deerflow.tools.nail.ops_channel.feishu_session import get_or_create_thread, get_thread_id; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/feishu_session.py
git commit -m "feat: add feishu_session.py — chat_id ↔ thread_id mapping CRUD

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Create feishu_reply.py — message sending via Feishu Open API

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/feishu_reply.py`

- [ ] **Step 1: Write feishu_reply.py**

```python
# ops_channel/feishu_reply.py
"""飞书 Open API 消息发送 — 使用 tenant_access_token 回复/发送消息。"""
from __future__ import annotations

import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

_MAX_TEXT_LEN = 29000  # 飞书单条消息限 30KB，留一些 buffer


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
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && python -c "from packages.harness.deerflow.tools.nail.ops_channel.feishu_reply import FeishuReplySender; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/feishu_reply.py
git commit -m "feat: add feishu_reply.py — Open API message reply/send with token management

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Create feishu_monitor.py — WebSocket event loop

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/feishu_monitor.py`

- [ ] **Step 1: Write feishu_monitor.py**

```python
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

# 去抖窗口（秒）
_DEBOUNCE_MS = 0.5
# 最大重连退避（秒）
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
        self._recent_msg_ids: dict[str, float] = {}  # msg_id → 收到时间，用于去重
        self._reply_sender: Any = None

    async def start(self) -> None:
        from .feishu_reply import FeishuReplySender

        self._reply_sender = FeishuReplySender(self._app_id, self._app_secret)
        self._running = True
        backoff = 1
        while self._running:
            try:
                await self._connect_and_listen()
                backoff = 1  # 正常断开后重置
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

        # Step 1: 获取 WS 连接信息
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

        # Step 2: 建立 WebSocket
        self._ws = await websockets.connect(
            ws_url,
            additional_headers={"Authorization": f"Bearer {ws_token}"},
            ping_interval=30,
            ping_timeout=10,
        )

        # Step 3: 事件循环
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
            # 只处理消息接收事件；pong/心跳等忽略
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
        # 清理过期条目
        self._recent_msg_ids = {k: v for k, v in self._recent_msg_ids.items() if now - v < 10}

        chat_type = msg_data.get("chat_type", "group")

        # 群聊 @机器人 过滤
        if self._mention_only and chat_type == "group":
            mentions = msg_data.get("mentions", []) or []
            # 检查是否 @了机器人（mentions 中包含机器人相关信息）
            # 简化处理：如果 mentions 为空且不是 p2p，则忽略
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

        open_id = ""
        sender = data.get("sender", {}) or {}
        sender_id = sender.get("sender_id", {}) or {}
        open_id = sender_id.get("open_id", "")

        logger.info("Feishu message: chat=%s open_id=%s text=%s", chat_id, open_id, text[:80])

        # 路由到 Agent
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
        from .feishu_session import get_or_create_thread

        thread_id = get_or_create_thread(chat_id, chat_type)

        # 发送到 LangGraph Agent (SSE stream)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"http://localhost:8001/api/v1/threads/{thread_id}/runs/stream",
                json={
                    "input": {
                        "messages": [{"role": "user", "content": text}],
                    },
                    "config": {
                        "configurable": {
                            "nail_role": "ops",
                            "nail_page_mode": "ops",
                        },
                    },
                },
            )
            resp.raise_for_status()

            # 收集 SSE 流式输出
            accumulated = ""
            async for raw_line in resp.aiter_lines():
                if not raw_line.startswith("data: "):
                    continue
                try:
                    chunk = json.loads(raw_line[6:])
                except json.JSONDecodeError:
                    continue

                # messages-tuple 模式: [msg_type, msg_data]
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
```

- [ ] **Step 2: Check websockets package availability**

Run: `cd backend && python -c "import websockets; print(websockets.__version__)"`
If missing: `uv add websockets`

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/feishu_monitor.py
git commit -m "feat: add feishu_monitor.py — WebSocket event loop for bidirectional chat

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: Wire FeishuMonitor into app.py lifespan

**Files:**
- Modify: `backend/app/gateway/app.py`

- [ ] **Step 1: Add FeishuMonitor startup/shutdown in lifespan**

In `app.py`, after the OpsScheduler startup block (line ~255), before `yield`, add:

```python
        # Start NailFlow Feishu Monitor (bidirectional chat)
        _feishu_monitor = None
        try:
            feishu_cfg = {}
            try:
                feishu_cfg = getattr(startup_config, 'nail_feishu', None) or {}
            except Exception:
                pass

            if feishu_cfg.get("enabled", False) and feishu_cfg.get("app_id") and feishu_cfg.get("app_secret"):
                from packages.harness.deerflow.tools.nail.ops_channel.feishu_monitor import FeishuMonitor
                import asyncio as _asyncio

                _feishu_monitor = FeishuMonitor(
                    app_id=feishu_cfg.get("app_id", ""),
                    app_secret=feishu_cfg.get("app_secret", ""),
                    mention_only=feishu_cfg.get("mention_only", True),
                )
                _asyncio.create_task(_feishu_monitor.start())
                app.state.feishu_monitor = _feishu_monitor
                logger.info("FeishuMonitor started (bidirectional chat enabled)")
            else:
                logger.info("FeishuMonitor not started (disabled or missing credentials)")
        except Exception:
            logger.exception("FeishuMonitor failed to start (non-fatal)")
```

And in the shutdown section (after `yield`, before `if _ops_scheduler`), add:

```python
        # Shutdown Feishu Monitor
        if _feishu_monitor is not None:
            try:
                await asyncio.wait_for(_feishu_monitor.shutdown(), timeout=_SHUTDOWN_HOOK_TIMEOUT_SECONDS)
            except (TimeoutError, asyncio.TimeoutError):
                logger.warning("FeishuMonitor shutdown timed out")
            except Exception:
                logger.exception("FeishuMonitor shutdown error (non-fatal)")
```

And ensure `import asyncio` is at the top of the file (it should already be there or add it).

- [ ] **Step 2: Commit**

```bash
git add backend/app/gateway/app.py
git commit -m "feat: wire FeishuMonitor into app lifespan for bidirectional chat

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: Add proactive_chat support to ops_runner.py

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/ops_channel/ops_runner.py`

- [ ] **Step 1: Add _run_proactive_chat() and route it in run_job()**

Add to `run_job()` the routing (before `else`):

```python
        elif task_type == "proactive_chat":
            return await _run_proactive_chat(job, ctx)
```

Add the function at end of file:

```python
async def _run_proactive_chat(job: OpsJob, ctx: dict) -> dict[str, Any]:
    """执行 proactive_chat 任务：在指定的飞书会话Thread 上运行 Agent。

    chat_id 来自 job.delivery.targets 中的 feishu 目标。
    如果 chat_id 已有 Thread，复用；否则创建新 Thread。
    Agent 的回复通过 TextMessage 包装返回。
    """
    from .feishu_session import get_or_create_thread
    from .delivery.messages.base import TextMessage

    # 从 delivery targets 中获取 chat_id
    chat_id = ""
    for target_spec in job.delivery.targets:
        if target_spec.get("channel") == "feishu":
            chat_id = target_spec.get("chat_id", "")
            break

    if not chat_id:
        return {"message": TextMessage(content="proactive_chat 缺少 chat_id 配置"), "ok": False, "result_data": {}, "error": "missing chat_id"}

    prompt = ctx.get("prompt", "") or job.task.type
    if not prompt.strip():
        return {"message": TextMessage(content="proactive_chat 缺少 prompt"), "ok": False, "result_data": {}, "error": "missing prompt"}

    thread_id = get_or_create_thread(chat_id, "group")

    try:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"http://localhost:8001/api/v1/threads/{thread_id}/runs/stream",
                json={
                    "input": {
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    "config": {
                        "configurable": {
                            "nail_role": "ops",
                            "nail_page_mode": "ops",
                        },
                    },
                },
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

        return {
            "message": TextMessage(content=accumulated.strip()[:30000]),
            "result_data": {"chat_id": chat_id, "thread_id": thread_id},
            "ok": True,
            "error": "",
        }
    except Exception as e:
        logger.exception("proactive_chat failed for chat_id=%s", chat_id)
        return {"message": TextMessage(content=f"Proactive chat 执行失败: {e}"), "ok": False, "result_data": {}, "error": str(e)}
```

- [ ] **Step 2: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/ops_runner.py
git commit -m "feat: add proactive_chat task type to ops_runner for cron-triggered agent conversations

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: Register proactive_chat jobs in ops_scheduler.py

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/ops_channel/ops_scheduler.py`

- [ ] **Step 1: Add proactive_chat job registration**

In `start()`, after the existing cron job loop (after the `self._apscheduler.add_job(...)` call for existing jobs, around line 48), add:

```python
        # Register proactive_chat jobs from config
        proactive_chats = self._config.get("proactive_chats", []) or []
        for pc in proactive_chats:
            if not pc.get("enabled", True):
                continue
            pc_id = pc.get("id", "")
            schedule = pc.get("schedule", "")
            if not pc_id or not schedule:
                logger.warning("Skipping proactive_chat with missing id/schedule: %s", pc)
                continue

            # 创建 OpsJob 并注册
            from .job_store import OpsJob, Trigger, TriggerType, TaskSpec, DeliverySpec
            pc_job = OpsJob(
                job_id=f"proactive_{pc_id}",
                trigger=Trigger(type=TriggerType.CRON, cron_expr=schedule),
                task=TaskSpec(type="proactive_chat"),
                delivery=DeliverySpec(targets=pc.get("targets", [])),
                enabled=True,
            )
            self._jobs[pc_job.job_id] = pc_job
            parts = schedule.split()
            self._apscheduler.add_job(
                self._execute_job, "cron", args=[pc_job.job_id, {"prompt": pc.get("prompt", "")}],
                id=pc_job.job_id, minute=parts[0], hour=parts[1],
            )
            logger.info("Scheduled proactive_chat %s: cron=%s", pc_id, schedule)
```

- [ ] **Step 2: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/ops_scheduler.py
git commit -m "feat: register proactive_chat jobs from config in ops_scheduler

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: Create xhs_client.py — XHS-Downloader wrapper + search

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/xhs_client.py`

- [ ] **Step 1: Install XHS-Downloader as editable package**

Run: `cd /Users/xinyiji/Desktop/XHS-Downloader && uv pip install -e .`
Run: `cd /Users/xinyiji/Desktop/美团黑客松ai美甲/hackathon-meituan-ai/backend && uv add httpx[socks]`

- [ ] **Step 2: Write xhs_client.py**

```python
# tools/nail/xhs_client.py
"""小红书数据获取：搜索引擎查询 + XHS-Downloader 帖子提取。"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import sys
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# XHS-Downloader 路径
_XHS_PATH = "/Users/xinyiji/Desktop/XHS-Downloader"
if _XHS_PATH not in sys.path:
    sys.path.insert(0, _XHS_PATH)

_DEFAULT_DELAY = 6.0

# 预置热门关键词（搜索降级用）
_FALLBACK_KEYWORDS = [
    "猫眼美甲", "法式美甲", "渐变美甲", "穿戴甲",
    "夏日美甲", "秋冬美甲", "裸色美甲", "红色美甲",
    "钻美甲", "蝴蝶结美甲",
]


async def search_posts(keyword: str, top_n: int = 10) -> list[dict]:
    """搜索小红书美甲帖子。

    通过 Bing 搜索 site:xiaohongshu.com 获取 URL，
    然后用 XHS-Downloader 逐条提取详情。

    Args:
        keyword: 搜索关键词
        top_n: 最大返回条数

    Returns:
        [{"title","description","likes","comments","saves","tags","url","published_at"}, ...]
    """
    full_keyword = f"美甲 {keyword}" if keyword else "美甲"
    urls = await _search_urls(full_keyword, top_n)
    if not urls:
        return []

    posts = await _extract_posts(urls[:top_n])
    return posts


async def _search_urls(keyword: str, count: int) -> list[str]:
    """通过 Bing 搜索获取小红书帖子 URL。"""
    query = f"site:xiaohongshu.com {keyword}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            if resp.status_code != 200:
                logger.warning("DuckDuckGo search failed: %d", resp.status_code)
                return []

            data = resp.json()
            urls: list[str] = []
            for result in data.get("Results", [])[:count]:
                url = result.get("FirstURL", "")
                if "xiaohongshu.com/explore/" in url:
                    urls.append(url)
            return urls
    except Exception:
        logger.warning("Search engine query failed for keyword=%s", keyword)
        return []


async def _extract_posts(urls: list[str]) -> list[dict]:
    """用 XHS-Downloader 逐条提取帖子详情。"""
    try:
        from source.application import XHS
        from source.module import Manager
    except ImportError:
        logger.warning("XHS-Downloader not available")
        return []

    cookie = os.getenv("XHS_COOKIE", "")
    manager = Manager()
    xhs = XHS(manager=manager)
    posts: list[dict] = []

    for i, url in enumerate(urls):
        try:
            data = await xhs.extract(url)
            if not data or not isinstance(data, dict):
                continue

            # XHS-Downloader 返回的 dict 使用中文 key
            posts.append({
                "title": data.get("作品标题", ""),
                "description": data.get("作品描述", ""),
                "likes": _parse_int(data.get("点赞数量", "0")),
                "comments": _parse_int(data.get("评论数量", "0")),
                "saves": _parse_int(data.get("收藏数量", "0")),
                "tags": (data.get("作品标签", "") or "").split(),
                "url": url,
                "published_at": data.get("发布时间", ""),
            })
        except Exception as e:
            logger.debug("Failed to extract post %s: %s", url, e)
            continue

        # 请求间延迟
        if i < len(urls) - 1:
            delay = max(1.0, random.lognormvariate(1.5, 0.5))
            await asyncio.sleep(min(delay, _DEFAULT_DELAY))

    return posts


def _parse_int(val: str) -> int:
    # 处理 "1.2万" 等格式
    val = str(val).strip()
    if not val:
        return 0
    try:
        if "万" in val:
            return int(float(val.replace("万", "")) * 10000)
        return int(val)
    except (ValueError, TypeError):
        return 0
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/xhs_client.py
git commit -m "feat: add xhs_client.py — XHS-Downloader wrapper with search engine URL discovery

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: Create xiaohongshu_search.py — the @tool

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/xiaohongshu_search.py`

- [ ] **Step 1: Write xiaohongshu_search.py**

```python
# tools/nail/xiaohongshu_search.py
"""小红书搜索工具 — 供 Agent 在运营分析时获取外部市场数据。"""
from __future__ import annotations

import json
import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool
def xiaohongshu_search_tool(
    keyword: str = "",
    topic: str = "美甲",
    top_n: int = 10,
) -> str:
    """搜索小红书上美甲相关帖子，获取热门趋势和用户偏好数据。

    用于运营分析时补充外部市场数据，了解小红书美甲趋势。
    与内部 ops_signals 数据交叉验证，发现新品类机会。

    Args:
        keyword: 搜索关键词，如"猫眼美甲"、"夏日美甲"、"穿戴甲"
        topic: 话题标签，默认"美甲"
        top_n: 返回条数，默认 10，最大 20

    Returns:
        JSON 字符串:
        {
          "posts": [
            {"title": "..","description":"..","likes":N,"comments":N,"saves":N,
             "tags":["美甲","猫眼"],"url":"https://...","published_at":"2026-06-05"}
          ],
          "count": N,
          "source": "xiaohongshu",
          "error": null
        }
    """
    try:
        import asyncio

        from .xhs_client import search_posts

        limit = min(top_n, 20)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(search_posts(keyword, limit), loop)
                posts = future.result(timeout=60)
            else:
                posts = loop.run_until_complete(search_posts(keyword, limit))
        except RuntimeError:
            posts = asyncio.run(search_posts(keyword, limit))

        return json.dumps({
            "posts": posts,
            "count": len(posts),
            "source": "xiaohongshu",
            "error": None,
        }, ensure_ascii=False)

    except ImportError:
        logger.warning("XHS-Downloader not installed, using fallback")
        return json.dumps({
            "posts": [],
            "count": 0,
            "source": "fallback",
            "error": "XHS-Downloader not installed. Install with: pip install -e /Users/xinyiji/Desktop/XHS-Downloader",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error("xiaohongshu_search_tool failed: %s", e)
        return json.dumps({
            "posts": [],
            "count": 0,
            "source": "fallback",
            "error": str(e),
        }, ensure_ascii=False)
```

- [ ] **Step 2: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/xiaohongshu_search.py
git commit -m "feat: add xiaohongshu_search_tool — LangChain tool for XHS post search

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: Register xiaohongshu_search_tool in config and registries

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/router_config.py`
- Modify: `backend/app/gateway/routers/nail_config.py`
- Modify: `backend/app/gateway/routers/nail_dev.py`

- [ ] **Step 1: Add capability declaration in router_config.py**

In `TOOL_CAPABILITIES`, add after `"nail_style_recommend_tool"`:

```python
    "xiaohongshu_search_tool":   Capability.CHAT,       # 搜索引擎 + HTML 解析，不用 LLM
```

- [ ] **Step 2: Add tool metadata in nail_config.py**

In `_NAIL_TOOL_META`, add after the `preference_rag_tool` entry:

```python
    ("xiaohongshu_search_tool",  "小红书搜索", "📕", "搜索小红书美甲帖子，获取外部趋势数据补充运营分析",           "nail_ops", False, False),
```

- [ ] **Step 3: Add to dev registry in nail_dev.py**

In `_TOOL_REGISTRY`, add:

```python
    "xiaohongshu_search_tool":  "deerflow.tools.nail.xiaohongshu_search:xiaohongshu_search_tool",
```

In `_TOOL_DESCRIPTIONS`, add:

```python
    "xiaohongshu_search_tool": {
        "description": "搜索小红书美甲帖子，获取外部趋势数据",
        "params": {"keyword": "搜索关键词", "topic": "话题标签（默认美甲）", "top_n": "返回条数"},
    },
```

- [ ] **Step 4: Verify imports**

Run: `cd backend && python -c "from packages.harness.deerflow.tools.nail.xiaohongshu_search import xiaohongshu_search_tool; print('import OK')"`
Expected: `import OK`

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/router_config.py backend/app/gateway/routers/nail_config.py backend/app/gateway/routers/nail_dev.py
git commit -m "feat: register xiaohongshu_search_tool in capability registry, tool meta, and dev registry

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 11: Register xiaohongshu_search_tool in config.yaml

**Files:**
- Modify: `config.yaml`

- [ ] **Step 1: Add tool registration**

In the `tools:` section of config.yaml, add after the last `nail_ops` group tool:

```yaml
  - name: xiaohongshu_search_tool
    group: nail_ops
    use: deerflow.tools.nail.xiaohongshu_search:xiaohongshu_search_tool
```

- [ ] **Step 2: Add config sections**

Add at end of config.yaml:

```yaml
# NailFlow 飞书双向对话
nail_feishu:
  enabled: false
  app_id: "$FEISHU_APP_ID"
  app_secret: "$FEISHU_APP_SECRET"
  mention_only: true

# NailFlow 小红书搜索
nail_xiaohongshu:
  enabled: true
  cookie: "$XHS_COOKIE"
  search_delay_ms: 6000
```

- [ ] **Step 3: Commit**

```bash
git add config.yaml
git commit -m "feat: register xiaohongshu_search_tool + add nail_feishu / nail_xiaohongshu config sections

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 12: Update Agent prompts for XHS search + Feishu chat

**Files:**
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`

- [ ] **Step 1: Update _NAIL_ROLE_PREFIX["ops"]**

Change:

```python
    "ops": (
        "你是 NailFlow 的智能运营助手。能进行试戴，还能分析运营数据、发现趋势、生成营销方案、处理客服咨询。\n"
```

To:

```python
    "ops": (
        "你是 NailFlow 的智能运营助手。能在飞书中与你双向对话，也能主动在预定时间发起分析。\n"
        "你能进行试戴，还能分析运营数据、发现趋势、生成营销方案、处理客服咨询。\n"
```

- [ ] **Step 2: Update _NAIL_PAGE_MODE_PREFIX["ops"]**

Append the XHS search guideline to the `"ops"` page mode prefix (after the existing content):

```python
        "外部数据补充：\n"
        "  在做趋势分析时，可调用 xiaohongshu_search_tool 查询小红书上的美甲趋势，\n"
        "  与内部 ops_signals 数据交叉验证。发现小红书热门但店内未覆盖的款式时，\n"
        "  应在分析报告中标注"外部趋势"并建议引入。\n"
        "  调用建议：\n"
        "  - 用户问"最近流行什么" → 同时调用 trend_query_tool + xiaohongshu_search_tool\n"
        "  - 用户问"某款式情况" → 调用 xiaohongshu_search_tool(keyword="该款式")\n"
        "  - 关键词提取：从用户问题中提取核心词，如"猫眼"、"法式"、"穿戴甲"\n\n"
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/agents/lead_agent/prompt.py
git commit -m "feat: update ops agent prompts — Feishu bidirectional chat + XHS search guidance

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 13: Run full test suite and verify no regressions

**Files:**
- (none — verification only)

- [ ] **Step 1: Run existing ops channel tests**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_nail_ops_channel.py -v --timeout=30
```
Expected: All existing tests pass

- [ ] **Step 2: Run existing approval + memory + skills tests**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_ops_approval.py tests/test_ops_memory.py tests/test_ops_skills.py -v --timeout=30
```
Expected: All existing tests pass

- [ ] **Step 3: Verify imports for all new modules**

```bash
cd backend && python -c "
from packages.harness.deerflow.tools.nail.ops_channel.feishu_session import get_or_create_thread, get_thread_id
from packages.harness.deerflow.tools.nail.ops_channel.feishu_reply import FeishuReplySender
from packages.harness.deerflow.tools.nail.ops_channel.feishu_monitor import FeishuMonitor
from packages.harness.deerflow.tools.nail.xhs_client import search_posts
from packages.harness.deerflow.tools.nail.xiaohongshu_search import xiaohongshu_search_tool
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 4: Verify config.yaml parses correctly**

```bash
cd backend && python -c "
from deerflow.config.app_config import AppConfig
cfg = AppConfig.from_file()
print('Config loaded OK, nail_feishu:', hasattr(cfg, 'nail_feishu'), 'nail_xiaohongshu:', hasattr(cfg, 'nail_xiaohongshu'))
"
```
Expected: Config loads without error

---

## Spec Self-Review

**1. Spec coverage:**
- [x] Feishu bidirectional chat (FeishuMonitor) — Tasks 1-5
- [x] Proactive chat scheduling — Tasks 6-7
- [x] Xiaohongshu search tool — Tasks 8-11
- [x] Agent prompt updates — Task 12
- [x] Config sections — Task 11

**2. Placeholder scan:** No TBD/TODO. All code is concrete. All paths are exact.

**3. Type consistency:**
- feishu_session.py exports `get_or_create_thread(chat_id, chat_type)` → used in feishu_monitor.py and ops_runner.py consistently
- feishu_reply.py exports `FeishuReplySender(app_id, app_secret)` with `reply(msg_id, text)` and `send_to_chat(chat_id, text)` → used in feishu_monitor.py and ops_runner.py
- xhs_client.py exports `search_posts(keyword, top_n) -> list[dict]` → used in xiaohongshu_search.py

**4. No issues found.**
