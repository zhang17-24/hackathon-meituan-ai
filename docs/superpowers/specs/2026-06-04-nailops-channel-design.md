# NailOps Channel — 运营端龙虾化设计

> 日期: 2026-06-04
> 状态: 设计完成，待实施
> 参考: OpenClaw 的 channel + cron + delivery 三层架构

## 一、目标

将 NailFlow 运营端从"被动 Web 看板"升级为"常驻多渠道 AI 运营助手"。

借鉴 OpenClaw 的核心架构模式：Channel（通道接入）→ Cron（定时/事件触发）→ Agent（执行分析）→ Delivery（多通道投递），在 NailFlow 内构建轻量级的"定时→Agent执行→通道投递"闭环。

## 二、分两期实施

| | 第一期（Push 流） | 第二期（Pull + Card 流） |
|---|---|---|
| 范围 | 定时日报推送 + 告警推送 | IM 双向对话 + 卡片交互确认 |
| 可演示 | 每天早上飞书收到日报卡片 | 飞书群内对话 + 按钮确认方案 |
| 依赖 | 飞书 Webhook URL | 飞书 Event Subscribe |

## 三、三层架构

```
Cron Layer    →  什么时间、因为什么触发
Agent Layer   →  做什么分析、生成什么内容
Delivery Layer → 投递到哪里、什么格式
```

### 3.1 Cron Layer

三种触发源：`cron`（定时）/ `interval`（间隔）/ `signal`（信号事件）/ `manual`（手动）

预置三 Jobs：

| job_id | trigger | task | delivery |
|--------|---------|------|----------|
| daily_report | cron: 0 9 * * * | 趋势+运营分析+日报格式化 | 飞书群 + Web看板 |
| trend_alert | signal: saves/hour > 3x baseline | 异常检测+告警格式化 | 飞书群 |
| manual_ops | manual | 解析IM指令→调用对应工具 | 原路返回 |

持久化表：

```sql
CREATE TABLE IF NOT EXISTS ops_job_runs (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- queued|running|delivered|failed
    trigger_type TEXT NOT NULL,
    payload TEXT,
    result TEXT,
    error TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
```

防重复执行：SQLite 行级乐观锁 `UPDATE ... WHERE status='queued'`。

### 3.2 Agent Layer

`ops_runner.py` 根据 job type 路由到已有工具链：

- `daily_report`: trend_discovery → ops_analysis → daily_report_formatter → 飞书卡片
- `trend_alert`: trend_query → 规则计算 → alert_formatter → 告警卡片
- `manual_ops`: 意图识别 → 对应工具 → 文本回复/卡片

格式化器输出结构化消息对象（Card/Text/Markdown），不依赖具体通道格式。

### 3.3 Delivery Layer

核心设计：**Adapter 注册制 + 能力声明 + 自动降级**

```python
class AbstractChannelAdapter(ABC):
    channel_id: str          # "feishu" | "web_push" | "wechat_mp" | ...
    capabilities: ChannelCapability  # TEXT | CARD | BUTTON | MARKDOWN | ...

    async def send(target: DeliveryTarget, message: AbstractMessage) -> DeliveryResult
    async def health_check() -> bool
```

通道能力声明 `ChannelCapability`（Flag 枚举）：TEXT / CARD / BUTTON / TEMPLATE / MARKDOWN / THREAD / FILE / MENTION

消息多态：
- `TextMessage` — 纯文本
- `CardMessage` — 交互式卡片（header + sections + buttons）
- `MarkdownMessage` — Markdown 渲染
- `TemplateMessage` — 模板消息（微信）

自动降级：卡片→Markdown→文本，依通道能力逐级退化。

配置驱动注册：

```yaml
nail_ops_channel:
  delivery:
    channels:
      feishu:
        adapter: "ops_channel.delivery.adapters.feishu:FeishuAdapter"
        enabled: true
        config:
          webhook_url: "$FEISHU_OPS_WEBHOOK_URL"
      web_push:
        adapter: "ops_channel.delivery.adapters.web_push:WebPushAdapter"
        enabled: true
```

拓展新通道只需：实现 `AbstractChannelAdapter` → config.yaml 注册 → 完成。不修改 router/registry/formatter。

### 3.4 数据流

**Push 流**：
```
cron触发 → create_run(queued) → OpsRunner.run() → Agent工具链
  → Formatter → AbstractMessage → ChannelRouter.deliver() → 自动降级 → Adapter.send()
  → update_run(delivered|failed)
```

**Pull 流（二期）**：
```
IM消息 → Webhook(POST /api/nail/ops/channel/{channel_id})
  → 签名验证 → parse_inbound → OpsRunner.run_manual(session_key, message)
  → Agent工具链 → Formatter → ChannelRouter.deliver(reply_target, reply_message)
```

**Card 流（二期）**：
```
卡片按钮点击 → 飞书回调 → POST /api/nail/ops/channel/feishu/card-action
  → dispatch_card_action(action_id, params) → 执行 → 更新卡片JSON
```

### 3.5 会话管理（二期）

`ops_sessions.py`：SQLite 存轻量会话上下文（session_key / last_tool_call / last_result_snippet / intent_hints），支持多轮对话：

```
运营: "本周爆款"        → trend_discovery → 爆款TOP3卡片
运营: "第一个做限时套餐"  → action_proposal  → 确认卡片
运营: "确认"             → proposal_executor → 卡片更新为"已执行"
```

## 四、文件清单

### 新增（17 文件，全部在 `ops_channel/` 包内）

```
backend/packages/harness/nailflow/tools/nail/ops_channel/
├── __init__.py
├── ops_scheduler.py          # Cron层：触发调度
├── ops_runner.py             # Agent层：任务路由+工具调用
├── ops_sessions.py           # Agent层：轻量会话管理 (二期)
├── job_store.py              # Cron层：job/run持久化
├── delivery/
│   ├── __init__.py
│   ├── base.py               # AbstractChannelAdapter + ChannelCapability + 类型
│   ├── registry.py           # AdapterRegistry 注册中心
│   ├── router.py             # ChannelRouter + 自动降级
│   ├── result_tracker.py     # 投递追踪
│   ├── messages/
│   │   ├── __init__.py
│   │   ├── base.py           # AbstractMessage / TextMessage / CardMessage / MarkdownMessage
│   │   └── card.py           # CardBuilder (CardHeader/CardSection/CardButton)
│   └── adapters/
│       ├── __init__.py
│       ├── feishu.py         # 飞书卡片+文本适配
│       └── web_push.py       # WebSocket → Web看板
└── formatters/
    ├── __init__.py
    ├── daily_report.py       # 日报格式化 → CardMessage
    └── alert_card.py         # 告警格式化 → CardMessage
```

### 修改

| 文件 | 改动 |
|------|------|
| `backend/app/gateway/app.py` | lifespan 启动 ops_scheduler |
| `backend/app/gateway/routers/nail_ops.py` | 新增 `/ops/channel/{id}` Webhook + WebSocket + 手动触发端点 |
| `config.yaml` | 新增 `nail_ops_channel` 配置段 |
| `backend/nail_scheduler.py` | 停止使用（保留文件不删除），功能迁移到 `ops_scheduler.py`，apscheduler 调用改为 `ops_scheduler` |

## 五、关键设计决策

1. **不新建 Agent** — ops_runner 是任务路由器，调用已有 5 个运营工具，只新增 formatter 层
2. **DeerFlow channel 只用于 Delivery 层** — 不侵入 Agent 层，agent 只产出 AbstractMessage
3. **Push 流第一期，Pull/Card 流第二期** — 最小可用先行，日报推送本身即可演示
4. **Adapter 注册制** — 飞书/WebPush 是首期两个 adapter，微信后续加
5. **自动降级** — 通道不支持卡片时自动降为 Markdown/纯文本，不发失败

## 六、配置示例

```yaml
nail_ops_channel:
  enabled: true
  jobs:
    daily_report:
      enabled: true
      schedule: "0 9 * * *"
      timezone: "Asia/Shanghai"
    trend_alert:
      enabled: true
      threshold: 3.0  # 超出基线倍数
  delivery:
    channels:
      feishu:
        adapter: "ops_channel.delivery.adapters.feishu:FeishuAdapter"
        enabled: true
        config:
          webhook_url: "$FEISHU_OPS_WEBHOOK_URL"
          app_id: "$FEISHU_APP_ID"
          app_secret: "$FEISHU_APP_SECRET"
      web_push:
        adapter: "ops_channel.delivery.adapters.web_push:WebPushAdapter"
        enabled: true
  sessions:
    ttl_minutes: 30
    max_per_channel: 50
```
