# OpenClaw 能力迁移到 NailFlow — 设计文档

> 状态：draft | 日期：2026-06-07

## 概述

将 OpenClaw 的三个核心系统（Skills 技能编排、Memory 持久化记忆、Human-in-the-loop 审批）用 Python 原生重写，融入 NailFlow 现有架构。

- **方式**：Python 原生重写，不引入 OpenClaw sidecar
- **渠道**：飞书/钉钉 Webhook 推送
- **范围**：分三阶段，日报 → 审批 → 记忆

---

## 一、架构

### 1.1 新增目录结构

```
backend/packages/harness/nailflow/ops/
├── __init__.py
├── skills/
│   ├── __init__.py
│   ├── manager.py          # SkillManager — 加载/注入/执行
│   ├── loader.py           # 扫描 skills/ 目录，解析 YAML frontmatter
│   └── models.py           # Skill dataclass
├── memory/
│   ├── __init__.py
│   ├── manager.py          # MemoryManager — MEMORY.md 读写 + SOUL.md 加载
│   ├── injector.py         # 中间件 — 每次 run 注入相关记忆
│   └── models.py           # MemoryEntry / MemoryIndex
├── approval/
│   ├── __init__.py
│   ├── manager.py          # ApprovalManager — 状态机 + 回滚
│   └── models.py           # ApprovalRecord / PendingAction
├── notify/
│   ├── __init__.py
│   ├── base.py             # NotificationAdapter 抽象基类
│   ├── feishu.py           # 飞书 Webhook → 交互卡片
│   ├── dingtalk.py         # 钉钉 Webhook
│   └── console.py          # 开发调试用
└── cron/
    ├── __init__.py
    ├── scheduler.py        # APScheduler 封装
    └── jobs/
        ├── daily_report.py # 日报 job
        └── trend_alert.py  # 爆款预警 job
```

### 1.2 与现有架构的关系

```
LangGraph Agent (lead_agent/agent.py)
         │
   ┌─────┼─────┐
   ▼     ▼     ▼
SkillMgr Memory 现有13个
         Injector nail tools
```

- 不改动现有 13 个 tool
- Skills 是 Markdown 上下文，注入 Agent system prompt，不是新的 tool 类型
- Memory 作为 LangGraph 中间件注入
- nail_role 权限体系复用 `_ROLE_GROUPS`

### 1.3 新增/扩展数据库表

```sql
-- 技能执行日志
CREATE TABLE skill_executions (
    id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    run_id TEXT,
    status TEXT DEFAULT 'running',  -- running/success/failed
    result TEXT,
    error TEXT,
    started_at TEXT,
    completed_at TEXT
);

-- 审批记录
CREATE TABLE approval_records (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL,
    action_type TEXT NOT NULL,       -- shelf_adjust/price_change/style_hide/batch_upload
    target JSON NOT NULL,
    previous_state JSON,             -- 回滚快照
    status TEXT DEFAULT 'pending',   -- pending/approved/rejected/expired/executed/rolled_back
    operator TEXT,
    reject_reason TEXT,
    rollback_reason TEXT,
    created_at TEXT,
    resolved_at TEXT,
    rollback_at TEXT
);

-- 扩展 ops_memory 表
ALTER TABLE ops_memory ADD COLUMN memory_type TEXT DEFAULT 'marketing';
-- memory_type: trend / marketing / risk / feedback
```

---

## 二、技能系统

### 2.1 设计决策

- Skill 是 Markdown 上下文文档，不是可执行函数
- Skill 告诉 Agent「什么场景、用什么工具、按什么步骤」
- Agent 自己编排工具调用链，Skill 只是指南
- 技能按 nail_role 过滤，和工具共用权限体系

### 2.2 SKILL.md 格式

```markdown
---
name: daily_report
description: 每日美甲运营日报生成与推送
group: nail_ops
version: v1
tools:
  - trend_query_tool
  - trend_discovery_tool
---

# 日报生成

## 触发条件
- 定时：每日 09:00
- 手动：运营人员在对话中说"生成日报"

## 执行流程
1. 调用 trend_query_tool(days=7, top_n=20) 获取趋势数据
2. 调用 trend_discovery_tool(days=7) 生成洞察报告
3. 按日报模板格式化输出
4. 通过通知渠道推送飞书/钉钉

## 输出模板
### NailFlow 运营日报
> {date} | 近 {days} 天数据

**数据概览**
- 总试戴量 / UV / 转化率

**热门款式 TOP 5**
...

**冷门预警**
...

**运营建议**
...
```

### 2.3 SkillManager 接口

```python
class SkillManager:
    def load_skills(self, group: str) -> list[Skill]
        # 扫描 skills/ 目录，解析 YAML frontmatter
        # 按 group 过滤（nail / nail_ops / nail_dev）

    def inject_context(self, skills: list[Skill]) -> str
        # 将技能列表格式化为 Agent system prompt 可用的 XML 块
        # 输出格式与 OpenClaw 的 formatSkillsForPrompt() 对齐

    def find_skill(self, name: str) -> Skill | None
        # 按名称查找单个技能

    def record_execution(self, skill_name: str, run_id: str, status: str, result: str) -> None
        # 写 skill_executions 表
```

### 2.4 技能加载路径

```
backend/packages/harness/nailflow/ops/skills/
  (代码管理 skills 目录)

data/skills/
  (运行时用户自定义 skills，优先加载)
```

加载优先级：`data/skills/` > `ops/skills/`（用户自定义覆盖内置）。

### 2.5 Agent 注入方式

在 `lead_agent/agent.py` 中，构建 system prompt 时：

```python
from nailflow.ops.skills.manager import SkillManager

skill_mgr = SkillManager()
skills = skill_mgr.load_skills(group=nail_groups)
skill_context = skill_mgr.inject_context(skills)

system_prompt = base_prompt + skill_context  # 技能上下文追加到 system prompt
```

---

## 三、记忆系统

### 3.1 设计决策

- SQLite 是主存储（与 CLAUDE.md 规范一致）
- MEMORY.md 是人可读索引（自动从 SQLite 生成）
- SOUL.md 是静态 Agent 人设（手动维护）
- 中间件在每次 Agent run 开始时注入记忆上下文

### 3.2 MEMORY.md 格式

```markdown
# NailFlow 运营记忆

## 趋势 (trend)
- [2026-06-01] 碎钻渐变 style_042 连续5天上升 → 标记爆款
- [2026-06-03] 纯色哑光系列整体下滑 → 建议降价

## 营销 (marketing)
- [2026-06-01] 六一亲子套餐：转化率 12%

## 反馈 (feedback)
- [2026-06-02] style_089 图片质量投诉 3 次 → 已下架

## 风险 (risk)
- [2026-06-04] 供应商 A 延迟交货，style_056 库存不足
```

### 3.3 SOUL.md 格式

```markdown
# 角色
你是美甲门店智能运营助手。

# 工作原则
- 数据敏感：异常波动 5 分钟内识别
- 决策谨慎：影响用户可见内容的操作必须人工确认
- 表达简洁：运营日报不超过 500 字
- 可追溯：所有操作记录操作人和时间

# 领域知识
- 美甲旺季：节假日、周末、换季期
- 爆款生命周期：通常 2-4 周
- 冷门阈值：连续 7 天用户信号 ≤ 1
- 价格敏感度：纯色款 < 渐变款 < 镶钻款
```

### 3.4 MemoryManager 接口

```python
class MemoryManager:
    def load_soul(self) -> str
        # 读取 SOUL.md，全量返回

    def load_memories(self, limit: int = 20, memory_type: str | None = None) -> list[MemoryEntry]
        # 从 SQLite 读取最近记忆

    def append(self, content: str, memory_type: str) -> str  # → entry_id
        # 写 SQLite + 更新 MEMORY.md

    def sync_md(self) -> None
        # 将 SQLite 中的记忆同步到 MEMORY.md 文件

    def summarize(self) -> None
        # 当记忆超过阈值（200 条），LLM 压缩旧条目为摘要
```

### 3.5 MemoryInjector 中间件

```python
class MemoryInjectorMiddleware:
    """在 Agent run 开始时注入 SOUL.md + 最近记忆。"""

    async def __call__(self, state: AgentState, config: dict) -> AgentState:
        soul = self.memory_mgr.load_soul()
        memories = self.memory_mgr.load_memories(limit=20)
        context = f"{soul}\n\n## 运营记忆\n" + "\n".join(m.text for m in memories)
        state["messages"].insert(0, SystemMessage(content=context))
        return state
```

注册到 DeerFlow 中间件栈，在 `SummarizationMiddleware` 之后、`ClarificationMiddleware` 之前。

---

## 四、审批系统

### 4.1 状态机

```
proposed → pending ──→ approved → executed → completed
              │            │
              ├→ rejected  └→ rolled_back → reverted
              └→ expired (24h 超时)
```

### 4.2 风险分级

| 风险等级 | 操作类型 | 审批策略 |
|---------|---------|---------|
| 低 | 推荐位排序调整、标签更新、数据报表 | 自动执行，仅记录日志 |
| 高 | 款式下架/隐藏、价格调整、批量上架 | 必须人工 approve |

### 4.3 ApprovalManager 接口

```python
class ApprovalManager:
    def propose(self, action_type: str, target: dict, payload: dict,
                risk: str = "high") -> str
        # 创建提案，低风险自动 approved，高风险 pending
        # 返回 proposal_id

    def approve(self, proposal_id: str, operator: str) -> bool
        # 状态 → approved → 执行 → executed

    def reject(self, proposal_id: str, operator: str, reason: str) -> bool
        # 状态 → rejected，记录原因

    def rollback(self, proposal_id: str, operator: str, reason: str) -> bool
        # 已 executed 的操作 → rolled_back
        # 通过 previous_state JSON 恢复原状态

    def list_pending(self) -> list[ApprovalRecord]
    def auto_expire(self) -> int
        # 超过 24h 的 pending → expired
```

### 4.4 飞书审批卡片

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {"title": {"content": "NailFlow 运营方案待审批", "tag": "plain_text"}},
    "elements": [
      {"tag": "div", "text": {"content": "**操作类型**：款式下架"}},
      {"tag": "div", "text": {"content": "**目标款式**：style_089（纯色哑光-酒红）"}},
      {"tag": "div", "text": {"content": "**原因**：连续 10 天用户信号为 0，图片质量问题投诉 3 次"}},
      {"tag": "hr"},
      {"tag": "action", "actions": [
        {"tag": "button", "text": {"content": "批准", "tag": "lark_md"}, "type": "primary",
         "value": {"proposal_id": "xxx", "action": "approve"}},
        {"tag": "button", "text": {"content": "拒绝", "tag": "lark_md"}, "type": "danger",
         "value": {"proposal_id": "xxx", "action": "reject"}}
      ]}
    ]
  }
}
```

**注意**：交互卡片回调需要公网可达的 API 端点。Phase 1 飞书仅发通知卡片（含 Dashboard 链接），审批操作在 Web Dashboard 完成。Phase 2 网络条件允许时再加交互卡片回调。

---

## 五、通知系统

### 5.1 抽象基类

```python
class NotificationAdapter(ABC):
    @abstractmethod
    async def send_markdown(self, title: str, content: str) -> bool: ...
    @abstractmethod
    async def send_card(self, card: dict) -> bool: ...
    @abstractmethod
    async def send_approval_request(self, proposal: ApprovalRecord) -> str: ...
```

### 5.2 渠道实现

| 实现 | 环境变量 | 说明 |
|------|---------|------|
| `FeishuAdapter` | `FEISHU_WEBHOOK_URL` | 飞书群机器人 Webhook |
| `DingTalkAdapter` | `DINGTALK_WEBHOOK_URL` | 钉钉群机器人 Webhook |
| `ConsoleAdapter` | 无 | 开发调试用，打印到 stdout |

### 5.3 工厂函数

```python
def get_notifier() -> NotificationAdapter:
    if os.getenv("FEISHU_WEBHOOK_URL"):
        return FeishuAdapter()
    if os.getenv("DINGTALK_WEBHOOK_URL"):
        return DingTalkAdapter()
    return ConsoleAdapter()  # 默认降级
```

---

## 六、定时任务

### 6.1 Job 定义

| Job | Cron | 功能 |
|-----|------|------|
| `daily_report` | `55 8 * * *` | 跑日报技能 → 格式化 → 推飞书 |
| `trend_alert` | `0 */6 * * *` | 跑爆款预警 → 有异常则推飞书 |
| `auto_expire` | `0 * * * *` | 超时 24h 的 pending → expired |

### 6.2 生命周期

在 `app.py` lifespan 中注册：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = get_scheduler()
    scheduler.add_job(daily_report_job, "cron", hour=8, minute=55)
    scheduler.add_job(trend_alert_job, "cron", hour="*/6")
    scheduler.add_job(auto_expire_job, "cron", minute=0)
    scheduler.start()
    yield
    scheduler.shutdown()
```

---

## 七、分阶段实施

### Phase 1 — 日报推送（核心）

**交付**：
- `ops/skills/` — SkillManager + 内置 `daily_report.skill.md`
- `ops/notify/` — NotificationAdapter + FeishuAdapter + ConsoleAdapter
- `ops/cron/` — APScheduler 封装 + daily_report job
- `ops/__init__.py` — 统一导出

**验证**：手动调用 `daily_report` 技能 → 飞书收到日报卡片

### Phase 2 — 审批流程

**交付**：
- `ops/approval/` — ApprovalManager + 状态机 + 回滚
- `approval_records` 表创建
- 飞书交互卡片（批准/拒绝按钮）
- Dashboard 页面审批 UI 增强

**验证**：生成方案 → 飞书收到卡片 → 点击批准 → 执行 → 数据库记录完整

### Phase 3 — 运营记忆

**交付**：
- `ops/memory/` — MemoryManager + MemoryInjector 中间件
- SOUL.md + MEMORY.md
- `ops_memory` 表扩展 `memory_type` 字段
- 记忆自动总结（LLM 压缩）

**验证**：多次对话后 → Agent 引用历史记忆 → MEMORY.md 自动更新

---

## 八、安全与降级

### 8.1 通知降级

```
FeishuAdapter 失败 → 重试 1 次 → 写日志 → ConsoleAdapter 兜底
```

### 8.2 审批安全

- 所有审批操作记录 `operator` + 时间戳
- 回滚保留原始 `previous_state`，不做物理删除
- Webhook 回调验证签名（飞书/钉钉标准验证）

### 8.3 记忆隐私

- SOUL.md 和 MEMORY.md 不包含用户个人信息
- 仅记录款式 ID、运营指标、营销效果
- 不入 `.gitignore` 的 `data/` 目录存放运行时记忆文件

---

## 九、与现有代码的改动点

| 文件 | 改动 |
|------|------|
| `agents/lead_agent/agent.py` | 注入 Skill 上下文到 system prompt |
| `agents/lead_agent/prompt.py` | 不修改，Skill 上下文追加在 prompt 末尾 |
| `tools/nail/base.py` | `init_nail_tables()` 新增两张表 |
| `app/gateway/app.py` | lifespan 注册 cron jobs |
| `app/gateway/routers/nail_ops.py` | 审批记录 API（已有 proposal confirm 接口，扩展） |

不改动任何现有 tool 文件。

---

*最后更新：2026-06-07*
