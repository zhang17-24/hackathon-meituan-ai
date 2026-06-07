# OpenClaw 能力迁移 Phase 1 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 OpenClaw 的 Skills 技能系统用 Python 原生重写，融入 NailFlow 现有 ops_channel 基础设施。

**Architecture:** 新建 `deerflow/ops/skills/` 目录实现 SKILL.md 加载器 + SkillManager，通过 agent.py 注入 Agent system prompt。扩展现有 `init_nail_tables()` 加 `skill_executions` 表。新增 DingTalk 适配器。

**Tech Stack:** Python 3.12+, LangGraph, DeerFlow 现有架构, apscheduler (已安装), httpx (已安装)

**前置现状：**
- ✅ `ops_channel/` — OpsScheduler, OpsJob, FeishuAdapter, ChannelRouter, ops_runner, daily_report/alert_card 格式化器全部就绪
- ✅ `app.py` lifespan — 已注册 daily_report (cron `0 9 * * *`) + trend_alert (signal) 两个 job
- ✅ `ops_channel/delivery/adapters/` — Feishu + WebPush 适配器已实现
- ✅ 日报推送全链路已跑通（scheduler → runner → trend_discovery → format_daily_report → FeishuAdapter.send）
- ❌ 缺少 Skills 系统（SKILL.md 加载/解析/Agent 注入）
- ❌ 缺少 DingTalk 适配器
- ❌ 缺少 `skill_executions` 表

---

## 文件结构

```
新建:
  backend/packages/harness/deerflow/ops/
  ├── __init__.py                        # 统一导出
  ├── skills/
  │   ├── __init__.py
  │   ├── models.py                      # Skill dataclass
  │   ├── loader.py                      # 扫描/解析 SKILL.md
  │   └── manager.py                     # SkillManager
  ├── approval/
  │   └── __init__.py                    # Phase 2 占位
  └── memory/
      └── __init__.py                    # Phase 3 占位

  data/skills/
  └── daily_report.skill.md              # 第一个技能文件

  backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/
  └── dingtalk.py                        # 钉钉适配器

修改:
  backend/packages/harness/deerflow/agents/lead_agent/agent.py   # 注入 skill 上下文
  backend/packages/harness/deerflow/tools/nail/base.py            # init_nail_tables() 加表
  backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/__init__.py  # 导出 DingTalkAdapter

测试:
  backend/tests/test_ops_skills.py        # 技能系统单测
```

---

### Task 1: Skill 数据模型

**Files:**
- Create: `backend/packages/harness/deerflow/ops/__init__.py`
- Create: `backend/packages/harness/deerflow/ops/skills/__init__.py`
- Create: `backend/packages/harness/deerflow/ops/skills/models.py`

- [ ] **Step 1: 创建目录结构和 Skill 数据类**

```bash
mkdir -p backend/packages/harness/deerflow/ops/skills
mkdir -p backend/packages/harness/deerflow/ops/approval
mkdir -p backend/packages/harness/deerflow/ops/memory
```

```python
# backend/packages/harness/deerflow/ops/__init__.py
"""NailFlow Ops — OpenClaw 能力迁移层。

Skills / Memory / Approval 三大系统，Python 原生实现。
"""
```

```python
# backend/packages/harness/deerflow/ops/skills/__init__.py
from .models import Skill
from .loader import SkillLoader
from .manager import SkillManager

__all__ = ["Skill", "SkillLoader", "SkillManager"]
```

```python
# backend/packages/harness/deerflow/ops/skills/models.py
"""Skill 数据模型 — 对齐 OpenClaw 的 SKILL.md frontmatter 格式。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Skill:
    """一个已解析的技能定义。

    对应 SKILL.md 的 YAML frontmatter + Markdown body。
    """
    name: str
    description: str
    group: str = "nail_ops"
    version: str = "v1"
    tools: list[str] = field(default_factory=list)
    body: str = ""           # frontmatter 之后的 Markdown 正文
    file_path: str = ""      # SKILL.md 文件路径
    source: str = "builtin"  # builtin / custom
```

- [ ] **Step 2: 提交**

```bash
git add backend/packages/harness/deerflow/ops/__init__.py \
        backend/packages/harness/deerflow/ops/skills/__init__.py \
        backend/packages/harness/deerflow/ops/skills/models.py \
        backend/packages/harness/deerflow/ops/approval/__init__.py \
        backend/packages/harness/deerflow/ops/memory/__init__.py
git commit -m "feat(ops): add Skill data model and ops/ directory skeleton"
```

---

### Task 2: Skill 加载器

**Files:**
- Create: `backend/packages/harness/deerflow/ops/skills/loader.py`
- Create: `data/skills/daily_report.skill.md`

- [ ] **Step 1: 写加载器**

```python
# backend/packages/harness/deerflow/ops/skills/loader.py
"""SKILL.md 文件扫描与 YAML frontmatter 解析。"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from .models import Skill

logger = logging.getLogger(__name__)

# 技能搜索路径（优先级从低到高）
_BUILTIN_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"
_CUSTOM_SKILLS_DIR = Path("data/skills")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


class SkillLoader:
    """扫描 skills/ 目录，解析 SKILL.md 文件。"""

    def __init__(self, builtin_dir: Path | None = None, custom_dir: Path | None = None):
        self._builtin_dir = builtin_dir or _BUILTIN_SKILLS_DIR
        self._custom_dir = custom_dir or _CUSTOM_SKILLS_DIR

    def load_all(self) -> list[Skill]:
        """加载所有技能，自定义目录覆盖内置同名技能。"""
        skills: dict[str, Skill] = {}

        for skill in self._scan_dir(self._builtin_dir, source="builtin"):
            skills[skill.name] = skill

        for skill in self._scan_dir(self._custom_dir, source="custom"):
            skills[skill.name] = skill  # 覆盖内置

        return list(skills.values())

    def load_by_group(self, group: str) -> list[Skill]:
        """按权限组加载技能。"""
        return [s for s in self.load_all() if s.group == group]

    def _scan_dir(self, directory: Path, source: str) -> list[Skill]:
        if not directory.exists():
            return []
        results: list[Skill] = []
        for md_file in sorted(directory.rglob("*.skill.md")):
            skill = self._parse_file(md_file, source)
            if skill:
                results.append(skill)
        return results

    def _parse_file(self, file_path: Path, source: str) -> Skill | None:
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read skill file %s: %s", file_path, e)
            return None

        match = _FRONTMATTER_RE.match(text)
        if not match:
            logger.warning("Skill file %s missing valid YAML frontmatter", file_path)
            return None

        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError as e:
            logger.warning("Skill file %s YAML parse error: %s", file_path, e)
            return None

        name = meta.get("name")
        if not name:
            logger.warning("Skill file %s missing required 'name' field", file_path)
            return None

        return Skill(
            name=name,
            description=meta.get("description", ""),
            group=meta.get("group", "nail_ops"),
            version=str(meta.get("version", "v1")),
            tools=meta.get("tools", []),
            body=match.group(2).strip(),
            file_path=str(file_path),
            source=source,
        )
```

- [ ] **Step 2: 创建第一个技能文件**

```bash
mkdir -p data/skills
```

```markdown
<!-- data/skills/daily_report.skill.md -->
---
name: daily_report
description: 每日美甲运营日报生成与推送 — 聚合趋势数据、生成洞察报告、格式化日报并推送到飞书/钉钉
group: nail_ops
version: v1
tools:
  - trend_query_tool
  - trend_discovery_tool
  - ops_analysis_tool
---

# 日报生成技能

## 触发条件
- 定时：每日 08:55 (APScheduler cron)
- 手动：运营人员在对话中说"生成日报"或"今天的数据怎么样"

## 执行流程
1. 调用 trend_query_tool(days=7, top_n=20) 获取近期趋势数据
2. 调用 trend_discovery_tool(days=7) 生成洞察报告（爆款/冷门识别）
3. 调用 ops_analysis_tool 基于洞察生成具体运营建议
4. 按日报模板格式化：数据概览 → 爆款TOP5 → 冷门预警 → 运营建议
5. 通过飞书/钉钉推送

## 输出模板

### NailFlow 运营日报
> {date} | 近 {days} 天数据

**数据概览**
- 追踪款式数 / 活跃信号数 / 爆款数 / 冷门预警数

**热门款式 TOP 5**
（含试戴量变化趋势和运营建议）

**冷门预警**
（连续低信号款式，建议下架或换封面）

**运营建议**
（基于 AI 分析的具体可执行建议）

## 注意事项
- 数据为空时推送"今日暂无足够数据"提示
- 周末数据量少时自动扩大窗口到 14 天
```

- [ ] **Step 3: 提交**

```bash
git add backend/packages/harness/deerflow/ops/skills/loader.py data/skills/daily_report.skill.md
git commit -m "feat(ops): add SkillLoader and first daily_report skill"
```

---

### Task 3: SkillManager

**Files:**
- Create: `backend/packages/harness/deerflow/ops/skills/manager.py`

- [ ] **Step 1: 写 SkillManager**

```python
# backend/packages/harness/deerflow/ops/skills/manager.py
"""SkillManager — 技能生命周期管理 + Agent 上下文注入。"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from .loader import SkillLoader
from .models import Skill

logger = logging.getLogger(__name__)


class SkillManager:
    """管理技能加载、注入 Agent 上下文、执行记录。

    注入格式对齐 OpenClaw 的 formatSkillsForPrompt() XML 布局。
    """

    def __init__(self, loader: SkillLoader | None = None):
        self._loader = loader or SkillLoader()
        self._cache: dict[str, list[Skill]] = {}

    def load_skills(self, groups: list[str] | None = None) -> list[Skill]:
        """加载技能，按 group 过滤。"""
        cache_key = ",".join(sorted(groups)) if groups else "all"
        if cache_key not in self._cache:
            all_skills = self._loader.load_all()
            if groups:
                group_set = set(groups)
                all_skills = [s for s in all_skills if s.group in group_set]
            self._cache[cache_key] = all_skills
        return self._cache[cache_key]

    def find_skill(self, name: str) -> Skill | None:
        for s in self.load_skills():
            if s.name == name:
                return s
        return None

    def inject_context(self, skills: list[Skill]) -> str:
        """将技能列表格式化为 system prompt 可追加的 XML 块。

        格式与 OpenClaw 的 formatSkillsForPrompt() 对齐，
        便于 Agent 解析和遵循。
        """
        if not skills:
            return ""

        lines = [
            "",
            "The following skills provide specialized instructions for specific tasks.",
            "When a skill matches the task, follow its steps using the listed tools.",
            "",
            "<available_skills>",
        ]
        for skill in skills:
            lines.append("  <skill>")
            lines.append(f"    <name>{self._escape_xml(skill.name)}</name>")
            lines.append(f"    <description>{self._escape_xml(skill.description)}</description>")
            if skill.tools:
                tools_str = ", ".join(skill.tools)
                lines.append(f"    <tools>{self._escape_xml(tools_str)}</tools>")
            lines.append(f"    <instructions>")
            # 注入 skill body 的前 2000 字符，避免 prompt 过长
            body_short = skill.body[:2000]
            lines.append(self._escape_xml(body_short))
            lines.append(f"    </instructions>")
            lines.append("  </skill>")
        lines.append("</available_skills>")

        return "\n".join(lines)

    def record_execution(self, skill_name: str, run_id: str | None,
                         status: str, result: str, error: str = "") -> str:
        """记录技能执行到 skill_executions 表。返回 execution_id。"""
        execution_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        try:
            from deerflow.tools.nail.base import get_db
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO skill_executions (id, skill_name, run_id, status, result, error, started_at, completed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (execution_id, skill_name, run_id, status, result, error, now, now),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to record skill execution: %s", e)
        return execution_id

    def invalidate_cache(self) -> None:
        self._cache.clear()

    @staticmethod
    def _escape_xml(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```

- [ ] **Step 2: 提交**

```bash
git add backend/packages/harness/deerflow/ops/skills/manager.py
git commit -m "feat(ops): add SkillManager with agent context injection"
```

---

### Task 4: 添加 skill_executions 表

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/base.py`

- [ ] **Step 1: 在 init_nail_tables() 中添加新表**

在现有 `CREATE TABLE IF NOT EXISTS nail_style_catalog` 之后追加：

```python
# 在 init_nail_tables() 的 conn.executescript() 字符串末尾追加:
conn.executescript("""
    ...

    CREATE TABLE IF NOT EXISTS skill_executions (
        id          TEXT PRIMARY KEY,
        skill_name  TEXT NOT NULL,
        run_id      TEXT,
        status      TEXT DEFAULT 'running',
        result      TEXT,
        error       TEXT,
        started_at  TEXT,
        completed_at TEXT
    );

    CREATE TABLE IF NOT EXISTS approval_records (
        id              TEXT PRIMARY KEY,
        proposal_id     TEXT NOT NULL,
        action_type     TEXT NOT NULL,
        target          TEXT NOT NULL,
        previous_state  TEXT,
        status          TEXT DEFAULT 'pending',
        operator        TEXT,
        reject_reason   TEXT,
        rollback_reason TEXT,
        created_at      TEXT,
        resolved_at     TEXT,
        rollback_at     TEXT
    );
""")
```

- [ ] **Step 2: 验证表创建**

```bash
cd backend && python -c "
from packages.harness.deerflow.tools.nail.base import init_nail_tables, get_db
init_nail_tables()
with get_db() as conn:
    tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
    print([t[0] for t in tables])
    assert 'skill_executions' in [t[0] for t in tables], 'skill_executions table missing'
    assert 'approval_records' in [t[0] for t in tables], 'approval_records table missing'
    print('OK - both tables created')
"
```

- [ ] **Step 3: 提交**

```bash
git add backend/packages/harness/deerflow/tools/nail/base.py
git commit -m "feat(ops): add skill_executions and approval_records tables"
```

---

### Task 5: 在 Agent 中注入 Skill 上下文

**Files:**
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/agent.py`

- [ ] **Step 1: 在 _build_system_prompt 或等效位置注入技能**

在 `make_lead_agent()` 函数中，构建 system prompt 时追加技能上下文。找到 `apply_prompt_template()` 调用点附近：

```python
# 在 make_lead_agent() 函数中，system_prompt 构建完成后追加:

from deerflow.ops.skills.manager import SkillManager

# NailFlow: 注入技能上下文
nail_role = cfg.get("nail_role", "user")
_ROLE_GROUPS = {
    "user": ["nail"],
    "ops":  ["nail", "nail_ops"],
    "dev":  ["nail", "nail_ops", "nail_dev"],
}
nail_groups = _ROLE_GROUPS.get(nail_role, ["nail"])

try:
    skill_mgr = SkillManager()
    skills = skill_mgr.load_skills(groups=nail_groups)
    skill_context = skill_mgr.inject_context(skills)
    if skill_context:
        system_prompt += "\n" + skill_context
except Exception:
    logger.warning("Failed to inject skill context (non-fatal)")
```

- [ ] **Step 2: 提交**

```bash
git add backend/packages/harness/deerflow/agents/lead_agent/agent.py
git commit -m "feat(ops): inject skill context into agent system prompt"
```

---

### Task 6: DingTalk 适配器

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/dingtalk.py`
- Modify: `backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/__init__.py`

- [ ] **Step 1: 写 DingTalk 适配器**

```python
# ops_channel/delivery/adapters/dingtalk.py
"""钉钉通道适配器：webhook 模式，支持 Markdown + 卡片。"""
from __future__ import annotations

import json
import logging
import time
import hmac
import hashlib
import base64
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
        self._secret = cfg.get("secret", "")       # 加签密钥
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
                "markdown": {"title": getattr(message, "title", "NailFlow"), "text": message.content},
            }
        elif isinstance(message, CardMessage):
            # 钉钉不支持飞书式交互卡片，转为 markdown
            lines = [f"### {message.header_title}"]
            for section in message.sections:
                if section.title:
                    lines.append(f"**{section.title}**")
                lines.extend(section.lines)
            return {"msgtype": "markdown", "markdown": {"title": message.header_title, "text": "\n\n".join(lines)}}
        else:
            content = message.content if isinstance(message, TextMessage) else str(message)
            return {"msgtype": "text", "text": {"content": content}}
```

- [ ] **Step 2: 更新 __init__.py 导出**

```python
# ops_channel/delivery/adapters/__init__.py
from .feishu import FeishuAdapter
from .web_push import WebPushAdapter
from .dingtalk import DingTalkAdapter
```

- [ ] **Step 3: 提交**

```bash
git add backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/dingtalk.py \
        backend/packages/harness/deerflow/tools/nail/ops_channel/delivery/adapters/__init__.py
git commit -m "feat(ops): add DingTalk webhook adapter"
```

---

### Task 7: 技能系统集成测试

**Files:**
- Create: `backend/tests/test_ops_skills.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/test_ops_skills.py
"""OpenClaw Skills 系统单元测试。"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 确保 backend/ 在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.harness.deerflow.ops.skills.models import Skill
from packages.harness.deerflow.ops.skills.loader import SkillLoader
from packages.harness.deerflow.ops.skills.manager import SkillManager


SAMPLE_SKILL_MD = """---
name: test_skill
description: A test skill
group: nail_ops
version: v1
tools:
  - tool_a
  - tool_b
---

# Test Skill

## Steps
1. Do something
2. Do something else
"""


class TestSkillLoader:
    def test_parse_valid_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_file = Path(tmp) / "test.skill.md"
            skill_file.write_text(SAMPLE_SKILL_MD, encoding="utf-8")
            loader = SkillLoader(builtin_dir=Path(tmp), custom_dir=Path("/nonexistent"))
            skills = loader.load_all()
            assert len(skills) == 1
            s = skills[0]
            assert s.name == "test_skill"
            assert s.description == "A test skill"
            assert s.group == "nail_ops"
            assert s.tools == ["tool_a", "tool_b"]
            assert "Test Skill" in s.body

    def test_parse_missing_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_file = Path(tmp) / "bad.skill.md"
            skill_file.write_text("---\ndescription: no name\n---\n# Body", encoding="utf-8")
            loader = SkillLoader(builtin_dir=Path(tmp), custom_dir=Path("/nonexistent"))
            skills = loader.load_all()
            assert len(skills) == 0

    def test_custom_overrides_builtin(self):
        with tempfile.TemporaryDirectory() as builtin_tmp, tempfile.TemporaryDirectory() as custom_tmp:
            (Path(builtin_tmp) / "a.skill.md").write_text(
                '---\nname: dup\nversion: v1\n---\n# Builtin', encoding="utf-8")
            (Path(custom_tmp) / "a.skill.md").write_text(
                '---\nname: dup\nversion: v2\n---\n# Custom', encoding="utf-8")
            loader = SkillLoader(builtin_dir=Path(builtin_tmp), custom_dir=Path(custom_tmp))
            skills = loader.load_all()
            assert len(skills) == 1
            assert skills[0].source == "custom"
            assert skills[0].version == "v2"


class TestSkillManager:
    def test_inject_context_empty(self):
        mgr = SkillManager()
        result = mgr.inject_context([])
        assert result == ""

    def test_inject_context_with_skills(self):
        mgr = SkillManager()
        skill = Skill(name="test", description="A test", group="nail_ops",
                      tools=["tool_a"], body="Some instructions")
        result = mgr.inject_context([skill])
        assert "<available_skills>" in result
        assert "<name>test</name>" in result
        assert "<description>A test</description>" in result
        assert "<tools>tool_a</tools>" in result
        assert "Some instructions" in result
        assert "</available_skills>" in result

    def test_inject_context_escapes_xml(self):
        mgr = SkillManager()
        skill = Skill(name="x&y", description="a<b>c", group="nail_ops")
        result = mgr.inject_context([skill])
        assert "x&amp;y" in result
        assert "a&lt;b&gt;c" in result

    def test_load_by_group_filters(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "ops.skill.md").write_text(
                '---\nname: ops_skill\ngroup: nail_ops\n---\n# Ops', encoding="utf-8")
            (Path(tmp) / "dev.skill.md").write_text(
                '---\nname: dev_skill\ngroup: nail_dev\n---\n# Dev', encoding="utf-8")
            loader = SkillLoader(builtin_dir=Path(tmp), custom_dir=Path("/nonexistent"))
            mgr = SkillManager(loader=loader)
            ops = mgr.load_skills(groups=["nail_ops"])
            assert len(ops) == 1
            assert ops[0].name == "ops_skill"
```

- [ ] **Step 2: 运行测试**

```bash
cd backend && PYTHONPATH=. uv run pytest tests/test_ops_skills.py -v
```

Expected: 6 tests PASS

- [ ] **Step 3: 提交**

```bash
git add backend/tests/test_ops_skills.py
git commit -m "test(ops): add skill system unit tests"
```

---

### Task 8: 端到端验证 — 日报技能全链路

- [ ] **Step 1: 手动加载技能验证**

```bash
cd backend && python -c "
from packages.harness.deerflow.ops.skills.loader import SkillLoader
loader = SkillLoader()
skills = loader.load_all()
print(f'Loaded {len(skills)} skills:')
for s in skills:
    print(f'  - {s.name} ({s.group}) [{s.source}]')
    print(f'    tools: {s.tools}')
    print(f'    body: {s.body[:100]}...')
"
```

Expected: 至少输出 `daily_report (nail_ops) [builtin]`

- [ ] **Step 2: 验证 Agent 上下文注入**

```bash
cd backend && python -c "
from packages.harness.deerflow.ops.skills.manager import SkillManager
mgr = SkillManager()
skills = mgr.load_skills(groups=['nail_ops'])
ctx = mgr.inject_context(skills)
print(f'Context length: {len(ctx)} chars')
print(ctx[:500])
"
```

Expected: 输出格式化的 XML 上下文，含 daily_report 技能信息

- [ ] **Step 3: 验证 ops_channel 日报链路仍正常工作**

```bash
cd backend && python -c "
import asyncio
from packages.harness.deerflow.tools.nail.ops_channel.ops_runner import run_job
from packages.harness.deerflow.tools.nail.ops_channel.job_store import OpsJob, TaskSpec

job = OpsJob(job_id='test_daily', task=TaskSpec(type='daily_report'))
result = asyncio.run(run_job(job, {'days': 7}))
print(f'ok={result[\"ok\"]}')
print(f'message type={type(result[\"message\"]).__name__}')
if result['ok']:
    from packages.harness.deerflow.tools.nail.ops_channel.delivery.messages.base import CardMessage
    if isinstance(result['message'], CardMessage):
        print(f'Card title: {result[\"message\"].header_title}')
"
```

Expected: `ok=True`, message 为 CardMessage，含日报数据

- [ ] **Step 4: 提交验证结果（如有代码调整）**

---

## Phase 2 预览（不在本次执行）

| Task | 交付 |
|------|------|
| ApprovalManager | 状态机 + approval_records 表操作 |
| 审批 API | `POST /api/nail/approvals/{id}/approve|reject|rollback` |
| Dashboard UI | 审批按钮 + 状态展示 |
| 回滚测试 | 集成测试 |

## Phase 3 预览（不在本次执行）

| Task | 交付 |
|------|------|
| MemoryManager | MEMORY.md 读写 + SOUL.md 加载 |
| MemoryInjector | LangGraph 中间件 |
| 记忆总结 | LLM 压缩旧条目 |
| 集成测试 | 端到端 |
