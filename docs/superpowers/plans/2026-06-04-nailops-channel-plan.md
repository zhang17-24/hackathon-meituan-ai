# NailOps Channel — 运营端龙虾化实施计划（第一期 Push 流）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现运营日报+告警 Push 推送到飞书/Web看板，建立 Cron→Agent→Delivery 三层架构基座

**Architecture:** 在 `ops_channel/` 包内新建 18 个文件，分层构建：消息类型 → Delivery 基座 → Formatter → JobStore → Runner → Scheduler → 集成入口。修改 4 个现有文件完成接入。

**Tech Stack:** Python 3.12+ / apscheduler 3.x / httpx / SQLite (job_run) / FastAPI WebSocket

---

### Task 1: 包骨架 + 消息类型 + Card 组件

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/__init__.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/__init__.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/messages/__init__.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/messages/base.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/messages/card.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/__init__.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/formatters/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/messages
mkdir -p backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters
mkdir -p backend/packages/harness/deerflow/tools/nail/ops_channel/formatters
touch backend/packages/harness/deerflow/tools/nail/ops_channel/__init__.py
touch backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/__init__.py
touch backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/messages/__init__.py
touch backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/__init__.py
touch backend/packages/harness/deerflow/tools/nail/ops_channel/formatters/__init__.py
```

- [ ] **Step 2: Write messages/base.py — message type hierarchy**

```python
# ops_channel/delivery/messages/base.py
"""消息类型层次：通道无关的标准化消息表示。"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageKind(Enum):
    TEXT = "text"
    CARD = "card"
    MARKDOWN = "markdown"
    TEMPLATE = "template"


@dataclass
class AbstractMessage:
    kind: MessageKind

    def to_primitive(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class TextMessage(AbstractMessage):
    content: str

    def __init__(self, content: str):
        self.kind = MessageKind.TEXT
        self.content = content

    def to_primitive(self) -> dict[str, Any]:
        return {"kind": "text", "content": self.content}


@dataclass
class MarkdownMessage(AbstractMessage):
    content: str

    def __init__(self, content: str):
        self.kind = MessageKind.MARKDOWN
        self.content = content

    def to_primitive(self) -> dict[str, Any]:
        return {"kind": "markdown", "content": self.content}


@dataclass
class CardMessage(AbstractMessage):
    """交互式卡片消息：header + sections + buttons。"""
    header_title: str
    header_color: str = "blue"
    sections: list["CardSection"] = field(default_factory=list)
    buttons: list["CardButton"] = field(default_factory=list)

    def __init__(
        self,
        header_title: str,
        header_color: str = "blue",
        sections: list["CardSection"] | None = None,
        buttons: list["CardButton"] | None = None,
    ):
        self.kind = MessageKind.CARD
        self.header_title = header_title
        self.header_color = header_color
        self.sections = sections or []
        self.buttons = buttons or []

    def to_primitive(self) -> dict[str, Any]:
        return {
            "kind": "card",
            "header": {"title": self.header_title, "color": self.header_color},
            "sections": [s.to_primitive() for s in self.sections],
            "buttons": [b.to_primitive() for b in self.buttons],
        }
```

- [ ] **Step 3: Write messages/card.py — card builder components**

```python
# ops_channel/delivery/messages/card.py
"""卡片构建组件：CardSection / CardButton。"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CardSection:
    title: str = ""
    lines: list[str] = field(default_factory=list)
    highlight_fields: dict[str, str] = field(default_factory=dict)

    def to_primitive(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.title:
            result["title"] = self.title
        if self.lines:
            result["lines"] = self.lines
        if self.highlight_fields:
            result["highlight_fields"] = self.highlight_fields
        return result


@dataclass
class CardButton:
    label: str
    action: str
    value: str = ""
    style: str = "default"

    def to_primitive(self) -> dict[str, Any]:
        return {"label": self.label, "action": self.action, "value": self.value, "style": self.style}
```

- [ ] **Step 4: Verify imports**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel.delivery.messages.base import TextMessage, CardMessage, MarkdownMessage
from packages.harness.deerflow.tools.nail.ops_channel.delivery.messages.card import CardSection, CardButton
m = TextMessage('hello'); print(m.to_primitive())
c = CardMessage('test', sections=[CardSection(title='S1', lines=['line1'])])
print(c.to_primitive())
"
```
Expected: `{'kind': 'text', 'content': 'hello'}` then card dict

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/
git commit -m "feat(ops-channel): add package scaffold + message type hierarchy + card builder"
```

---

### Task 2: Delivery 基座类型

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/base.py`

- [ ] **Step 1: Write delivery/base.py**

```python
# ops_channel/delivery/base.py
"""Delivery 基座：ChannelCapability / DeliveryTarget / AbstractChannelAdapter / DeliveryResult。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Flag, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .messages.base import AbstractMessage


class ChannelCapability(Flag):
    TEXT = auto()
    CARD = auto()
    BUTTON = auto()
    TEMPLATE = auto()
    MARKDOWN = auto()
    THREAD = auto()
    FILE = auto()
    MENTION = auto()


@dataclass
class DeliveryTarget:
    channel: str
    recipient: str
    thread_id: str | None = None
    account_id: str | None = None


@dataclass
class DeliveryResult:
    ok: bool
    channel: str
    message_id: str = ""
    error: str = ""


class AbstractChannelAdapter(ABC):
    @property
    @abstractmethod
    def channel_id(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> ChannelCapability: ...

    @abstractmethod
    async def send(self, target: DeliveryTarget, message: "AbstractMessage") -> DeliveryResult: ...

    async def health_check(self) -> bool:
        return True
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel.delivery.base import ChannelCapability, DeliveryTarget, DeliveryResult, AbstractChannelAdapter
print(ChannelCapability.CARD | ChannelCapability.TEXT)
"
```
Expected: `ChannelCapability.TEXT|CARD`

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/base.py
git commit -m "feat(ops-channel): add delivery base types (ChannelCapability, DeliveryTarget, AbstractChannelAdapter)"
```

---

### Task 3: Delivery Registry + Router + Result Tracker

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/registry.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/router.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/result_tracker.py`

- [ ] **Step 1: Write delivery/registry.py**

```python
# ops_channel/delivery/registry.py
"""适配器注册中心：配置驱动加载 + 能力查询。"""
from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import AbstractChannelAdapter, ChannelCapability

logger = logging.getLogger(__name__)


class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, "AbstractChannelAdapter"] = {}

    def register(self, adapter: "AbstractChannelAdapter") -> None:
        self._adapters[adapter.channel_id] = adapter
        logger.info("Registered channel adapter: %s", adapter.channel_id)

    def get(self, channel_id: str) -> "AbstractChannelAdapter | None":
        return self._adapters.get(channel_id)

    def list_all(self) -> list[str]:
        return list(self._adapters.keys())

    def list_capable(self, capability: "ChannelCapability") -> list[str]:
        result = []
        for cid, ad in self._adapters.items():
            if capability in ad.capabilities:
                result.append(cid)
        return result

    def load_from_config(self, channels_config: dict) -> None:
        for channel_id, cfg in channels_config.items():
            if not cfg.get("enabled", True):
                logger.info("Channel %s disabled, skipping", channel_id)
                continue
            adapter_path = cfg.get("adapter", "")
            if not adapter_path:
                continue
            try:
                module_path, class_name = adapter_path.split(":")
                # resolve relative path to absolute
                if module_path.startswith("ops_channel."):
                    module_path = "packages.harness.deerflow.tools.nail." + module_path
                mod = importlib.import_module(module_path)
                adapter_cls = getattr(mod, class_name)
                adapter = adapter_cls(config=cfg.get("config", {}))
                self.register(adapter)
            except Exception:
                logger.exception("Failed to load adapter for channel %s", channel_id)
```

- [ ] **Step 2: Write delivery/router.py**

```python
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
        from .messages.base import CardMessage, MarkdownMessage, MessageKind, TextMessage

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
```

- [ ] **Step 3: Write delivery/result_tracker.py**

```python
# ops_channel/delivery/result_tracker.py
"""投递结果追踪：记录到 ops_job_runs.result JSON 字段。"""
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import DeliveryResult

logger = logging.getLogger(__name__)


def record_delivery(run_id: str, channel: str, result: "DeliveryResult") -> None:
    try:
        from ....base import get_db
        with get_db() as conn:
            row = conn.execute("SELECT result FROM ops_job_runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                return
            existing = {}
            if row["result"]:
                try:
                    existing = json.loads(row["result"])
                except json.JSONDecodeError:
                    pass
            deliveries = existing.get("deliveries", {})
            deliveries[channel] = {"ok": result.ok, "message_id": result.message_id, "error": result.error}
            existing["deliveries"] = deliveries
            conn.execute("UPDATE ops_job_runs SET result = ? WHERE id = ?",
                         (json.dumps(existing, ensure_ascii=False), run_id))
            conn.commit()
    except Exception:
        logger.exception("record_delivery failed for run %s channel %s", run_id, channel)
```

- [ ] **Step 4: Verify imports**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel.delivery.registry import AdapterRegistry
from packages.harness.deerflow.tools.nail.ops_channel.delivery.router import ChannelRouter
from packages.harness.deerflow.tools.nail.ops_channel.delivery.result_tracker import record_delivery
print('Delivery layer OK')
"
```
Expected: `Delivery layer OK`

- [ ] **Step 5: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/registry.py backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/router.py backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/result_tracker.py
git commit -m "feat(ops-channel): add delivery registry, router with auto-degrade, result tracker"
```

---

### Task 4: Job Store — 持久化 + 乐观锁 + ops_job_runs 表

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/job_store.py`
- Modify: `backend/packages/harness/deerflow/tools/nail/base.py` — `init_nail_tables()` 新增表

- [ ] **Step 1: Add ops_job_runs table to init_nail_tables()**

In `backend/packages/harness/deerflow/tools/nail/base.py`, inside `init_nail_tables()` method, inside the `conn.executescript("""...""")` call, add after the last `CREATE INDEX` statement and before the closing `"""`:

```sql

            CREATE TABLE IF NOT EXISTS ops_job_runs (
                id           TEXT PRIMARY KEY,
                job_id       TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'queued',
                trigger_type TEXT NOT NULL,
                payload      TEXT,
                result       TEXT,
                error        TEXT,
                created_at   TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );
```

- [ ] **Step 2: Write job_store.py**

```python
# ops_channel/job_store.py
"""Job 定义与 run 记录持久化。"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    CRON = "cron"
    INTERVAL = "interval"
    SIGNAL = "signal"
    MANUAL = "manual"


@dataclass
class DeliverySpec:
    targets: list[dict] = field(default_factory=list)


@dataclass
class TaskSpec:
    type: str = ""


@dataclass
class Trigger:
    type: TriggerType
    cron_expr: str = ""
    signal_threshold: float = 3.0


@dataclass
class OpsJob:
    job_id: str
    trigger: Trigger
    task: TaskSpec
    delivery: DeliverySpec
    enabled: bool = True


def create_run(job_id: str, trigger_type: TriggerType, payload: dict | None = None) -> str:
    from ....base import get_db
    run_id = str(uuid.uuid4())
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO ops_job_runs (id, job_id, status, trigger_type, payload) VALUES (?,?,?,?,?)",
                (run_id, job_id, "queued", trigger_type.value, json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()
        return run_id
    except Exception:
        logger.exception("create_run failed for job %s", job_id)
        return ""


def acquire_run(run_id: str) -> bool:
    from ....base import get_db
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "UPDATE ops_job_runs SET status='running' WHERE id=? AND status='queued'", (run_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        logger.exception("acquire_run failed for %s", run_id)
        return False


def complete_run(run_id: str, ok: bool, result_data: dict | None = None, error: str = "") -> None:
    from ....base import get_db
    status = "delivered" if ok else "failed"
    try:
        with get_db() as conn:
            conn.execute(
                "UPDATE ops_job_runs SET status=?, result=?, error=?, completed_at=datetime('now') WHERE id=?",
                (status, json.dumps(result_data or {}, ensure_ascii=False), error, run_id),
            )
            conn.commit()
    except Exception:
        logger.exception("complete_run failed for %s", run_id)


def get_baseline_signal_count(style_id: str, days: int = 7) -> float:
    from ....base import get_db
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM ops_signals WHERE style_id=? AND created_at>=datetime('now',?)",
                (style_id, f"-{days} days"),
            ).fetchone()
        count = row["cnt"] if row else 0
        return max(count / days, 1.0)
    except Exception:
        return 1.0
```

- [ ] **Step 3: Init tables and verify**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.base import init_nail_tables; init_nail_tables()
from packages.harness.deerflow.tools.nail.ops_channel.job_store import create_run, acquire_run, complete_run, TriggerType
rid = create_run('daily_report', TriggerType.CRON)
assert rid
assert acquire_run(rid)
complete_run(rid, True, {'test': True})
print('JobStore OK')
"
```
Expected: `JobStore OK`

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/job_store.py backend/packages/harness/deerflow/tools/nail/base.py
git commit -m "feat(ops-channel): add job_store with ops_job_runs table + optimistic locking"
```

---

### Task 5: Feishu Adapter

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/feishu.py`

- [ ] **Step 1: Write feishu.py**

```python
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
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel.delivery.adapters.feishu import FeishuAdapter
a = FeishuAdapter(config={'webhook_url': 'https://example.test'})
assert a.channel_id == 'feishu'
print('Feishu adapter OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/feishu.py
git commit -m "feat(ops-channel): add feishu adapter (card + text via webhook)"
```

---

### Task 6: WebPush Adapter (内存队列)

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/web_push.py`

- [ ] **Step 1: Write web_push.py**

```python
# ops_channel/delivery/adapters/web_push.py
"""Web 看板推送适配器：内存队列 → WebSocket 拉取。"""
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
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel.delivery.adapters.web_push import WebPushAdapter, get_recent_messages
a = WebPushAdapter()
assert a.channel_id == 'web_push'
print('WebPush adapter OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/web_push.py
git commit -m "feat(ops-channel): add web_push adapter (in-memory queue for WebSocket)"
```

---

### Task 7: Formatters — 日报 + 告警

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/formatters/daily_report.py`
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/formatters/alert_card.py`

- [ ] **Step 1: Write formatters/daily_report.py**

```python
# ops_channel/formatters/daily_report.py
"""日报格式化：趋势数据 + 运营方案 → CardMessage。"""
from __future__ import annotations
from typing import Any
from ..delivery.messages.base import CardMessage
from ..delivery.messages.card import CardButton, CardSection


def format_daily_report(trend_data: dict[str, Any], actions_data: dict[str, Any], days: int = 7) -> CardMessage:
    sections: list[CardSection] = []

    hot = trend_data.get("hot_styles", [])[:3]
    if hot:
        lines = []
        for i, s in enumerate(hot, 1):
            sid = s.get("style_id", "?")
            reason = s.get("reason", "")
            action = s.get("suggested_action", "")
            lines.append(f"{i}. {sid} — {reason} → {action}")
        sections.append(CardSection(title="📈 爆款 TOP3", lines=lines))

    cold = trend_data.get("cold_styles", [])[:2]
    if cold:
        lines = [f"· {s.get('style_id','?')} — {s.get('reason','')}" for s in cold]
        sections.append(CardSection(title="⚠️ 冷门预警", lines=lines))

    summary = trend_data.get("trend_summary", "")
    if summary:
        sections.append(CardSection(title="📊 趋势摘要", lines=[summary]))

    actions = actions_data.get("marketing_actions", [])[:2]
    if actions:
        lines = [f"· {a.get('title','')} — {a.get('reason','')} (预期: {a.get('expected_metric','')})" for a in actions]
        sections.append(CardSection(title="💡 运营建议", lines=lines))

    source = trend_data.get("data_source", f"近{days}日运营信号")
    sections.append(CardSection(title="📎 数据来源", lines=[source]))

    buttons = [
        CardButton(label="查看详情", action="view_detail", value="daily_report"),
        CardButton(label="手动刷新", action="refresh_report", value="daily_report"),
    ]

    return CardMessage(header_title=f"美甲运营日报 | {days}日趋势", header_color="pink", sections=sections, buttons=buttons)
```

- [ ] **Step 2: Write formatters/alert_card.py**

```python
# ops_channel/formatters/alert_card.py
"""告警格式化：信号突增 → CardMessage。"""
from __future__ import annotations
from ..delivery.messages.base import CardMessage
from ..delivery.messages.card import CardButton, CardSection


def format_trend_alert(style_id: str, current_count: int, baseline: float, multiplier: float, style_name: str = "") -> CardMessage:
    display_name = style_name or f"款式 {style_id}"
    sections: list[CardSection] = [
        CardSection(
            title="🚨 爆款告警",
            lines=[f"{display_name} ({style_id}) 信号异常飙升", ""],
            highlight_fields={"1小时内信号": str(current_count), "基线均值": f"{baseline:.1f}", "超出倍数": f"{multiplier:.1f}x"},
        ),
        CardSection(title="建议操作", lines=["· 核实数据真实性（排除刷量）", "· 如真实爆款 → 生成限时套餐", "· 检查库存/美甲师排期"]),
    ]
    buttons = [
        CardButton(label="查看款式", action="view_detail", value=style_id, style="primary"),
        CardButton(label="生成限时套餐", action="create_promotion", value=style_id),
        CardButton(label="忽略", action="ignore_alert", value=style_id, style="default"),
    ]
    return CardMessage(header_title=f"爆款告警: {display_name}", header_color="red", sections=sections, buttons=buttons)
```

- [ ] **Step 3: Verify formatters**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel.formatters.daily_report import format_daily_report
from packages.harness.deerflow.tools.nail.ops_channel.formatters.alert_card import format_trend_alert
trend = {'hot_styles': [{'style_id':'cow_french','reason':'收藏+12','suggested_action':'限时套餐'}], 'cold_styles': [], 'trend_summary': 'test', 'data_source': 'test'}
actions = {'marketing_actions': [{'title':'限时套餐','reason':'高信号','expected_metric':'+15%'}]}
card = format_daily_report(trend, actions)
print(card.header_title)
alert = format_trend_alert('cow_french', 15, 3.0, 5.0, '奶牛纹法式')
print(alert.header_title)
print('Formatters OK')
"
```
Expected: card title + alert title + `Formatters OK`

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/formatters/
git commit -m "feat(ops-channel): add daily_report + alert_card formatters"
```

---

### Task 8: Ops Runner — Agent 层任务路由器

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/ops_runner.py`

- [ ] **Step 1: Write ops_runner.py**

```python
# ops_channel/ops_runner.py
"""Agent 层任务路由器：调用已有运营工具 + 格式化输出。"""
from __future__ import annotations

import json
import logging
from typing import Any

from .delivery.messages.base import AbstractMessage, TextMessage
from .job_store import OpsJob

logger = logging.getLogger(__name__)


async def run_job(job: OpsJob, trigger_context: dict | None = None) -> dict[str, Any]:
    """执行一个 job，返回 {message, result_data, ok, error}。"""
    ctx = trigger_context or {}
    task_type = job.task.type
    try:
        if task_type == "daily_report":
            return await _run_daily_report(ctx)
        elif task_type == "trend_alert":
            return await _run_trend_alert(ctx)
        elif task_type == "manual_ops":
            return await _run_manual_ops(ctx)
        else:
            return {"message": None, "result_data": {}, "ok": False, "error": f"Unknown task: {task_type}"}
    except Exception as e:
        logger.exception("run_job(%s) failed", job.job_id)
        return {"message": TextMessage(content=f"任务执行失败: {e}"), "result_data": {}, "ok": False, "error": str(e)}


async def _run_daily_report(ctx: dict) -> dict[str, Any]:
    from ...trend_discovery import trend_discovery_tool
    from ...ops_analysis import ops_analysis_tool
    from .formatters.daily_report import format_daily_report

    days = ctx.get("days", 7)

    trend_raw = trend_discovery_tool.run({"days": days})
    trend_data = json.loads(trend_raw)
    if trend_data.get("error"):
        return {"message": TextMessage(content=f"趋势分析失败: {trend_data['error']}"), "ok": False, "result_data": {}, "error": trend_data.get("error")}

    actions_raw = ops_analysis_tool.run({"trend_summary": json.dumps(trend_data, ensure_ascii=False)})
    actions_data = json.loads(actions_raw)

    card = format_daily_report(trend_data, actions_data, days)

    return {"message": card, "result_data": {"trend": trend_data, "actions": actions_data}, "ok": True, "error": ""}


async def _run_trend_alert(ctx: dict) -> dict[str, Any]:
    from .formatters.alert_card import format_trend_alert

    style_id = ctx.get("style_id", "")
    current_count = ctx.get("current_count", 0)
    baseline = ctx.get("baseline", 1.0)
    multiplier = current_count / max(baseline, 0.1)

    card = format_trend_alert(style_id=style_id, current_count=current_count, baseline=baseline, multiplier=round(multiplier, 1))

    return {"message": card, "result_data": {"style_id": style_id, "current_count": current_count, "baseline": baseline, "multiplier": multiplier}, "ok": True, "error": ""}


async def _run_manual_ops(ctx: dict) -> dict[str, Any]:
    user_message = ctx.get("user_message", "")

    if any(kw in user_message for kw in ["爆款", "趋势", "热门"]):
        from ...trend_discovery import trend_discovery_tool
        raw = trend_discovery_tool.run({"days": 7})
        data = json.loads(raw)
        hot = data.get("hot_styles", [])[:3]
        lines = [f"**近7日爆款 TOP{min(len(hot),3)}**", ""]
        for i, s in enumerate(hot, 1):
            lines.append(f"{i}. {s.get('style_id','?')} — {s.get('reason','')}")
        return {"message": TextMessage(content="\n".join(lines)), "ok": True, "result_data": {}, "error": ""}

    elif any(kw in user_message for kw in ["方案", "运营", "营销"]):
        from ...ops_analysis import ops_analysis_tool
        raw = ops_analysis_tool.run({"trend_summary": "", "query": user_message})
        data = json.loads(raw)
        actions = data.get("marketing_actions", [])
        lines = ["**运营建议**", ""]
        for a in actions:
            lines.append(f"· {a.get('title','')} — {a.get('reason','')}")
        return {"message": TextMessage(content="\n".join(lines)), "ok": True, "result_data": {}, "error": ""}

    else:
        return {"message": TextMessage(content=f"收到指令: {user_message}\n支持: 爆款趋势 / 运营方案"), "ok": True, "result_data": {}, "error": ""}
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel.ops_runner import run_job
print('OpsRunner imported OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/ops_runner.py
git commit -m "feat(ops-channel): add ops_runner — task router for daily_report/trend_alert/manual_ops"
```

---

### Task 9: Ops Scheduler — Cron 层主进程

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/ops_scheduler.py`

- [ ] **Step 1: Write ops_scheduler.py**

```python
# ops_channel/ops_scheduler.py
"""调度器主进程：Cron 触发 → Agent 执行 → Delivery 投递。"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class OpsScheduler:
    def __init__(self, runner, router, job_store, jobs: list | None = None, config: dict | None = None):
        self._runner = runner
        self._router = router
        self._job_store = job_store
        self._jobs: dict[str, Any] = {}
        self._apscheduler = None
        self._config = config or {}
        if jobs:
            for job in jobs:
                self._jobs[job.job_id] = job

    def register_job(self, job) -> None:
        self._jobs[job.job_id] = job

    def start(self) -> None:
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
        except ImportError:
            logger.warning("apscheduler not installed, cron scheduling disabled")
            return

        self._apscheduler = AsyncIOScheduler(timezone=self._config.get("timezone", "Asia/Shanghai"))
        jobs_config = self._config.get("jobs", {})

        for job_id, job in self._jobs.items():
            if not job.enabled:
                continue
            if job.trigger.type.value == "cron" and job.trigger.cron_expr:
                job_cfg = jobs_config.get(job_id, {})
                if not job_cfg.get("enabled", True):
                    continue
                self._apscheduler.add_job(
                    self._execute_job, "cron", args=[job_id, {}], id=job_id,
                    minute=job.trigger.cron_expr.split()[0],
                    hour=job.trigger.cron_expr.split()[1],
                )
                logger.info("Scheduled job %s: cron=%s", job_id, job.trigger.cron_expr)

        self._apscheduler.start()
        logger.info("OpsScheduler started with %d cron jobs", len(self._apscheduler.get_jobs()))

    def shutdown(self) -> None:
        if self._apscheduler:
            self._apscheduler.shutdown(wait=False)
            logger.info("OpsScheduler shut down")

    def trigger(self, job_id: str, context: dict | None = None) -> None:
        ctx = context or {}
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._execute_job(job_id, ctx))
            else:
                loop.run_until_complete(self._execute_job(job_id, ctx))
        except RuntimeError:
            asyncio.run(self._execute_job(job_id, ctx))

    async def _execute_job(self, job_id: str, context: dict) -> None:
        job = self._jobs.get(job_id)
        if job is None:
            logger.error("Unknown job_id: %s", job_id)
            return

        from .job_store import TriggerType
        trigger_type = TriggerType.CRON if job.trigger.type.value == "cron" else TriggerType.SIGNAL

        run_id = self._job_store.create_run(job_id, trigger_type, context)
        if not run_id:
            return
        if not self._job_store.acquire_run(run_id):
            logger.info("Job %s run %s already acquired, skipping", job_id, run_id)
            return

        from .ops_runner import run_job as execute_task
        result = await execute_task(job, context)

        deliveries_ok = True
        for target_spec in job.delivery.targets:
            from .delivery.base import DeliveryTarget
            target = DeliveryTarget(channel=target_spec["channel"], recipient=target_spec.get("recipient", ""))
            message = result.get("message")
            if message is None:
                continue
            delivery_result = await self._router.deliver(target, message)
            from .delivery.result_tracker import record_delivery
            record_delivery(run_id, target.channel, delivery_result)
            if not delivery_result.ok:
                deliveries_ok = False

        self._job_store.complete_run(run_id, ok=result.get("ok", False) and deliveries_ok,
                                     result_data=result.get("result_data", {}), error=result.get("error", ""))
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel.ops_scheduler import OpsScheduler
print('OpsScheduler imported OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/ops_scheduler.py
git commit -m "feat(ops-channel): add ops_scheduler — cron trigger → agent execute → delivery loop"
```

---

### Task 10: Integration — app.py + config.yaml + nail_ops.py + __init__.py

**Files:**
- Modify: `backend/app/gateway/app.py` — lifespan section
- Modify: `config.yaml` — add `nail_ops_channel` config
- Modify: `backend/app/gateway/routers/nail_ops.py` — add endpoints
- Modify: `backend/packages/harness/deerflow/tools/nail/ops_channel/__init__.py` — public API

- [ ] **Step 1: Update __init__.py**

```python
# ops_channel/__init__.py (overwrite the empty file)
"""NailOps Channel — 运营端龙虾化子系统。"""
from .job_store import OpsJob, TaskSpec, Trigger, TriggerType, DeliverySpec, create_run, acquire_run, complete_run
from .ops_runner import run_job
from .ops_scheduler import OpsScheduler
from .delivery.registry import AdapterRegistry
from .delivery.router import ChannelRouter
from .delivery.base import DeliveryTarget, DeliveryResult
```

- [ ] **Step 2: Add nail_ops_channel config to config.yaml**

Append to `config.yaml`:

```yaml
# NailOps Channel — 运营端龙虾化
nail_ops_channel:
  enabled: true
  timezone: "Asia/Shanghai"
  jobs:
    daily_report:
      enabled: true
      schedule: "0 9 * * *"
    trend_alert:
      enabled: true
      threshold: 3.0
  delivery:
    channels:
      feishu:
        adapter: "ops_channel.delivery.adapters.feishu:FeishuAdapter"
        enabled: false
        config:
          webhook_url: "$FEISHU_OPS_WEBHOOK_URL"
      web_push:
        adapter: "ops_channel.delivery.adapters.web_push:WebPushAdapter"
        enabled: true
        config: {}
  sessions:
    ttl_minutes: 30
    max_per_channel: 50
```

- [ ] **Step 3: Modify app.py lifespan — replace nail_scheduler with OpsScheduler**

In `backend/app/gateway/app.py`, replace lines 201-206 and the yield+shutdown with:

```python
        # Start NailOps Channel (龙虾化运营调度)
        _ops_scheduler = None
        try:
            ops_cfg = {}
            try:
                ops_cfg = getattr(startup_config, 'nail_ops_channel', None) or {}
            except Exception:
                pass

            if ops_cfg.get("enabled", True):
                from packages.harness.deerflow.tools.nail.ops_channel import (
                    OpsScheduler, OpsJob, TaskSpec, Trigger, TriggerType, DeliverySpec,
                    AdapterRegistry, ChannelRouter, run_job,
                )
                import packages.harness.deerflow.tools.nail.ops_channel.job_store as _js

                feishu_cfg = ops_cfg.get("delivery", {}).get("channels", {}).get("feishu", {})
                feishu_webhook = feishu_cfg.get("config", {}).get("webhook_url", "") if feishu_cfg.get("enabled") else ""

                daily_job = OpsJob(
                    job_id="daily_report",
                    trigger=Trigger(type=TriggerType.CRON, cron_expr="0 9 * * *"),
                    task=TaskSpec(type="daily_report"),
                    delivery=DeliverySpec(targets=[
                        {"channel": "web_push", "recipient": "all"},
                        {"channel": "feishu", "recipient": feishu_webhook},
                    ]),
                )

                alert_job = OpsJob(
                    job_id="trend_alert",
                    trigger=Trigger(type=TriggerType.SIGNAL, signal_threshold=3.0),
                    task=TaskSpec(type="trend_alert"),
                    delivery=DeliverySpec(targets=[
                        {"channel": "web_push", "recipient": "all"},
                        {"channel": "feishu", "recipient": feishu_webhook},
                    ]),
                )

                registry = AdapterRegistry()
                registry.load_from_config(ops_cfg.get("delivery", {}).get("channels", {}))
                router = ChannelRouter(registry)

                _ops_scheduler = OpsScheduler(
                    runner=run_job,
                    router=router,
                    job_store=_js,
                    jobs=[daily_job, alert_job],
                    config=ops_cfg,
                )
                _ops_scheduler.start()
                app.state.ops_scheduler = _ops_scheduler
                logger.info("NailOps Channel started with daily_report + trend_alert jobs")
        except Exception:
            logger.exception("NailOps Channel failed to start (non-fatal)")

        yield

        # Shutdown NailOps Channel
        if _ops_scheduler is not None:
            _ops_scheduler.shutdown()
```

- [ ] **Step 4: Add API endpoints to nail_ops.py**

Append to `backend/app/gateway/routers/nail_ops.py`:

```python
# ─── NailOps Channel 接口 ────────────────────────────────────

@router.post("/ops/trigger/{job_id}")
@require_auth
async def trigger_ops_job(job_id: str, request: Request):
    """手动触发运营 Job。"""
    from packages.harness.deerflow.tools.nail.ops_channel import OpsScheduler
    sched = getattr(request.app.state, "ops_scheduler", None)
    if sched is None:
        raise HTTPException(status_code=503, detail="OpsScheduler not running")
    if job_id not in ("daily_report", "trend_alert", "manual_ops"):
        raise HTTPException(status_code=400, detail=f"Unknown job: {job_id}")
    sched.trigger(job_id, {"trigger_type": "manual"})
    return {"triggered": job_id, "status": "queued"}


@router.get("/ops/messages")
async def get_ops_messages(since: float = 0):
    """拉取 WebPush 消息（HTTP 轮询 / WebSocket 降级）。"""
    from packages.harness.deerflow.tools.nail.ops_channel.delivery.adapters.web_push import get_recent_messages
    return {"messages": get_recent_messages(since)}
```

- [ ] **Step 5: Verify the integration imports**

```bash
cd backend && uv run python -c "
from packages.harness.deerflow.tools.nail.ops_channel import OpsScheduler, OpsJob, TaskSpec, Trigger, TriggerType, DeliverySpec, AdapterRegistry, ChannelRouter, run_job
print('Full integration import OK')
"
```

- [ ] **Step 6: Dry-run the full scheduler pipeline (no actual delivery)**

```bash
cd backend && uv run python -c "
import asyncio
from packages.harness.deerflow.tools.nail.ops_channel import OpsScheduler, OpsJob, TaskSpec, Trigger, TriggerType, DeliverySpec, AdapterRegistry, ChannelRouter, run_job
import packages.harness.deerflow.tools.nail.ops_channel.job_store as _js

job = OpsJob(job_id='test_report', trigger=Trigger(type=TriggerType.CRON, cron_expr='0 9 * * *'), task=TaskSpec(type='daily_report'), delivery=DeliverySpec(targets=[{'channel':'web_push','recipient':'all'}]))
registry = AdapterRegistry()
registry.load_from_config({'web_push': {'adapter': 'packages.harness.deerflow.tools.nail.ops_channel.delivery.adapters.web_push:WebPushAdapter', 'enabled': True, 'config': {}}})
router = ChannelRouter(registry)
scheduler = OpsScheduler(runner=run_job, router=router, job_store=_js, jobs=[job])
# 手动触发一次
scheduler.trigger('test_report', {'trigger_type': 'manual', 'days': 1})
await asyncio.sleep(2)
from packages.harness.deerflow.tools.nail.ops_channel.delivery.adapters.web_push import get_recent_messages
msgs = get_recent_messages()
print(f'Messages in web_push inbox: {len(msgs)}')
for m in msgs:
    print(f'  {m[\"kind\"]}: {m[\"payload\"].get(\"header\",{}).get(\"title\",\"\")}')
scheduler.shutdown()
"
```
Expected: report with title in web_push inbox

- [ ] **Step 7: Commit**

```bash
git add backend/app/gateway/app.py config.yaml backend/app/gateway/routers/nail_ops.py backend/packages/harness/deerflow/tools/nail/ops_channel/__init__.py
git commit -m "feat(ops-channel): integrate OpsScheduler into app.py lifespan + config + API endpoints"
```

---

## Verification Checklist (post-implementation)

- [ ] `cd backend && uv run python -c "from packages.harness.deerflow.tools.nail.ops_channel import *"` — all imports clean
- [ ] `ops_job_runs` table exists after `init_nail_tables()`
- [ ] Manual trigger via `POST /api/nail/ops/trigger/daily_report` returns 200
- [ ] `GET /api/nail/ops/messages` returns pushed messages from web_push inbox
- [ ] OpsScheduler starts without error during app lifespan
- [ ] `FEISHU_OPS_WEBHOOK_URL` env set → feishu adapter sends successfully (or graceful failure if URL invalid)
- [ ] Old `nail_scheduler.py` no longer imported in app.py
