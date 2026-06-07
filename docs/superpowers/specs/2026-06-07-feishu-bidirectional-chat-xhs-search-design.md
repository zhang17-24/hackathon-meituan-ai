# NailFlow 飞书双向对话 + 定时主动聊天 + 小红书数据 设计文档

> 日期：2026-06-07 | 状态：设计完成

---

## 一、背景与目标

### 现状

当前 NailFlow 的飞书集成是**纯单向**的：通过群机器人 Webhook 推送日报卡片和告警消息到飞书群。无法接收飞书消息、无法对话、无会话状态。

### 目标

1. **飞书双向对话**：运营人员在飞书群 @机器人 提问，Agent 实时回复，复用 NailFlow 已有 ops 工具链
2. **定时主动聊天**：Agent 在预定时间主动在飞书群发起分析（如每日早报），群成员可后续追问，保持上下文
3. **小红书数据**：Agent 可搜索小红书美甲帖子，补充运营分析数据源

### 参考

- OpenClaw (`/Users/xinyiji/Desktop/openclaw`)：飞书双向通信的 WebSocket 连接模式、会话管理
- XHS-Downloader (`/Users/xinyiji/Desktop/XHS-Downloader`)：小红书帖子数据提取的 HTML 解析方法

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  NailFlow Backend (FastAPI + LangGraph)                      │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │  FeishuMonitor   │  │  OpsScheduler    │                  │
│  │  (WebSocket长连接) │  │  (APScheduler)   │                  │
│  │  - 接收消息事件    │  │  - daily_report  │                  │
│  │  - 去抖去重       │  │  - trend_alert   │                  │
│  │  - 会话映射       │  │  - proactive_chat│ ← 新增          │
│  └────────┬─────────┘  └────────┬─────────┘                  │
│           │                     │                             │
│           └──────────┬──────────┘                             │
│                      ▼                                        │
│  ┌──────────────────────────────────────────┐                │
│  │        LangGraph Thread Manager           │                │
│  │  每个 chat_id = 一个 Thread               │                │
│  │  feishu_sessions(chat_id, thread_id)      │                │
│  └────────────────────┬─────────────────────┘                │
│                       ▼                                       │
│  ┌──────────────────────────────────────────┐                │
│  │           Lead Agent (已有)                │                │
│  │  nail_role="ops"                          │                │
│  │  nail_page_mode="ops"                     │                │
│  │  tools: trend_query, ops_analysis,        │                │
│  │         customer_service,                  │                │
│  │         xiaohongshu_search ← 新增          │                │
│  └────────────────────┬─────────────────────┘                │
│                       ▼                                       │
│  ┌──────────────────────────────────────────┐                │
│  │         FeishuReplySender                  │                │
│  │  POST /open-apis/im/v1/messages/{id}/reply│                │
│  └──────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、飞书双向通信 — FeishuMonitor

### 3.1 连接方式

使用飞书开放平台的 **WebSocket 长连接**模式，与 OpenClaw 做法一致。

```
飞书开放平台
  │  wss://open.feishu.cn/open-apis/ws/info
  │  需要: APP_ID + APP_SECRET (从飞书开发者后台获取)
  │  事件类型: im.message.receive_v1
  ▼
FeishuMonitor (asyncio 后台任务, lifespan 启动)
```

### 3.2 FeishuMonitor 生命周期

```
start()
  ├─ 获取 tenant_access_token (用 APP_ID + APP_SECRET)
  ├─ 建立 WebSocket 连接到飞书 WS 网关
  ├─ 启动心跳 (每 30s ping)
  ├─ 启动事件接收循环
  │    ├─ 解析 JSON 事件
  │    ├─ 签名验证
  │    ├─ 过滤: 只处理 im.message.receive_v1
  │    ├─ 去抖: 500ms 内同 msg_id 跳过
  │    └─ 分发到 handle_message()
  └─ 断线自动重连 (指数退避: 1s → 2s → 4s → ... → 最大 60s)

shutdown()
  └─ 关闭 WebSocket, 清理资源
```

### 3.3 消息处理流程

```
handle_message(event)
  │
  ├─ 提取字段:
  │    open_id  = event.sender.sender_id.open_id
  │    chat_id  = event.message.chat_id
  │    content  = event.message.content (JSON string, 提取 text)
  │    msg_id   = event.message.message_id
  │    chat_type= event.message.chat_type (p2p / group)
  │
  ├─ 群聊过滤:
  │    如果 FEISHU_MENTION_ONLY=true 且 chat_type=group:
  │      检查 mentions[] 是否包含机器人 open_id, 否则忽略
  │
  ├─ 会话查找/创建:
  │    SELECT thread_id FROM feishu_sessions WHERE chat_id=?
  │    如果不存在 → POST /api/v1/threads 创建新 Thread
  │                 → INSERT INTO feishu_sessions
  │
  ├─ 构造 Agent 输入:
  │    POST /api/v1/threads/{thread_id}/runs/stream
  │    {
  │      input: { messages: [{role:"user", content: text}] },
  │      config: {
  │        configurable: {
  │          nail_role: "ops",
  │          nail_page_mode: "ops"
  │        }
  │      }
  │    }
  │
  ├─ 收集 SSE 流式输出 → 拼接完整回复
  │
  └─ 通过飞书 Open API 回复:
       POST /open-apis/im/v1/messages/{msg_id}/reply
       { content: { json: markdown_card } }
```

### 3.4 会话管理

**feishu_sessions 表：**

```sql
CREATE TABLE IF NOT EXISTS feishu_sessions (
    chat_id      TEXT PRIMARY KEY,    -- 飞书群/用户 chat_id
    thread_id    TEXT NOT NULL,       -- LangGraph Thread ID
    chat_type    TEXT DEFAULT 'group',-- p2p / group
    created_at   TEXT DEFAULT (datetime('now')),
    last_active  TEXT DEFAULT (datetime('now'))
);
```

- **会话粒度**：一个飞书群 = 一个 LangGraph Thread，群内所有人共享上下文
- **Thread 复用**：无论是主动定时聊天还是被动回复，同一个 chat_id 始终映射到同一个 Thread
- **生命周期**：Thread 不自动删除，由 LangGraph Checkpoint 管理历史

### 3.5 回复方式

```python
# 飞书回复消息 API
POST https://open.feishu.cn/open-apis/im/v1/messages/{root_msg_id}/reply
Authorization: Bearer {tenant_access_token}
Content-Type: application/json

{
  "content": "{\"text\":\"回复内容...\"}",
  "msg_type": "text"
}
```

- 使用**回复消息**（而非新消息），保持群聊线程清晰
- Agent 回复完成后一次性发送（不做流式逐字更新）
- 长文本自动分段（飞书单条消息限 30KB）

### 3.6 新增/修改文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `tools/nail/ops_channel/feishu_monitor.py` | WebSocket 连接管理 + 事件循环 |
| 新增 | `tools/nail/ops_channel/feishu_session.py` | 会话映射 CRUD |
| 新增 | `tools/nail/ops_channel/feishu_reply.py` | 飞书 Open API 回复发送 |
| 修改 | `base.py` `init_nail_tables()` | 新增 feishu_sessions 表 |
| 修改 | `app.py` lifespan | 启动/关闭 FeishuMonitor |
| 修改 | `config.yaml` | 新增 nail_feishu 配置段 |

### 3.7 配置设计

```yaml
# config.yaml 新增段
nail_feishu:
  enabled: true
  app_id: "$FEISHU_APP_ID"
  app_secret: "$FEISHU_APP_SECRET"
  mention_only: true           # 群聊中只响应 @机器人 的消息
  max_retry: 5
```

---

## 四、定时主动聊天 — Proactive Chat

### 4.1 设计思路

扩展现有 `OpsScheduler`，新增 `task.type = "proactive_chat"`。与 `daily_report` 的关键区别：

| | daily_report (现有) | proactive_chat (新增) |
|---|---|---|
| 执行方式 | 直接调用 trend_discovery_tool + ops_analysis_tool | 创建 LangGraph Thread Run，Agent 自主决定调用哪些工具 |
| 输出形式 | 格式化 CardMessage 推送 | Agent 自由文本回复（Markdown） |
| 上下文 | 无状态，每次独立 | 同一个 chat_id 复用 Thread，保留上下文供后续追问 |
| 触发 | cron | cron (可配置) |

### 4.2 配置定义

```yaml
# config.yaml
nail_ops_channel:
  proactive_chats:
    - id: "morning_briefing"
      enabled: true
      schedule: "0 9 * * *"            # 每天 09:00
      prompt: >
        请生成今日运营早报：
        1. 分析近24小时趋势信号，识别新增爆款和异常波动
        2. 对比近7天数据，标注涨跌趋势
        3. 列出需要关注的冷门款式（信号数≤1）
        4. 给出一条可执行的运营建议
      targets:
        - channel: "feishu"
          chat_id: "oc_xxx"            # 飞书群 ID
```

### 4.3 执行流程

```
1. APScheduler 触发 proactive_chat job
2. ops_runner._run_proactive_chat(job, context):
   a. 从 feishu_sessions 查找 chat_id 对应的 thread_id
      如果不存在 → 创建新 Thread (使用 job 中的初始 prompt 作为第一条消息)
      如果已存在 → 在已有 Thread 上发送 prompt 消息
   b. 等待 Agent 执行完成 (收集 SSE 流)
   c. 通过 FeishuReplySender 发送回复到飞书群
3. 后续用户追问 → 因为同一个 chat_id → thread_id 映射,
   直接在同一个 Thread 上继续,Agent 有之前的日报上下文
```

### 4.4 关键决策

- **首次执行时 Thread 的创建方式**：用 prompt 作为第一条 user message 发送 run，Agent 的自然语言回复 = 日报内容
- **复用已有 Thread**：如果群里之前聊过天（被动对话创建的 Thread），proactive_chat 直接在同一个 Thread 上继续，Agent 能记住之前的对话
- **不再使用 CardMessage**：proactive_chat 的输出是 Agent 自由生成的 Markdown 文本（更自然），而非固定结构的 CardMessage

### 4.5 新增/修改文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `ops_runner.py` | 新增 `_run_proactive_chat()` |
| 修改 | `ops_scheduler.py` | 从 config 读取 proactive_chats，注册为 cron job |
| 修改 | 前端 `ops-channel-settings-page.tsx` | 可配置 proactive_chats |

---

## 五、小红书数据 — xiaohongshu_search_tool

### 5.1 数据获取方式

**第一步：通过搜索引擎获取帖子 URL 列表**

```
site:xiaohongshu.com 美甲 猫眼 → 解析搜索结果
→ ["https://www.xiaohongshu.com/explore/xxx", ...]
```

**第二步：调用 XHS-Downloader 提取详情**

XHS-Downloader 的核心提取逻辑（`/Users/xinyiji/Desktop/XHS-Downloader/source/application/app.py`）：

```python
from source.application import XHS

xhs = XHS()
# 访问帖子 HTML → 提取 __INITIAL_STATE__ JSON → 解析字段
data = await xhs.extract("https://www.xiaohongshu.com/explore/xxx")
# data 包含: 作品标题, 作品描述, 点赞数量, 评论数量, 收藏数量,
#           分享数量, 作品标签, 发布时间, 作者昵称
```

### 5.2 工具定义

```python
@tool
def xiaohongshu_search_tool(
    keyword: str = "",
    topic: str = "美甲",
    days: int = 7,
    top_n: int = 10,
) -> str:
    """搜索小红书上美甲相关帖子，获取热门趋势和用户偏好数据。

    用于运营分析时补充外部市场数据，了解小红书美甲趋势。

    Args:
        keyword: 搜索关键词，如"猫眼美甲"、"夏日美甲"、"穿戴甲"
        topic: 话题标签，默认"美甲"
        days: 关注最近多少天的帖子
        top_n: 返回条数，默认 10

    Returns:
        JSON 字符串:
        {
          "posts": [
            {
              "title": "帖子标题",
              "description": "帖子描述",
              "likes": 1234,
              "comments": 56,
              "saves": 78,
              "tags": ["美甲", "猫眼"],
              "url": "https://...",
              "published_at": "2026-06-05"
            }
          ],
          "trend_summary": "基于搜索结果的趋势摘要",
          "count": 10
        }
    """
```

### 5.3 降级路径

```
主路径:
  搜索引擎 → URL列表 → XHS.extract() 逐条提取 → 聚合返回

降级1 (搜索不可用):
  使用预置的热门关键词列表 + XHS.extract() 固定URL

降级2 (XHS 提取失败):
  仅返回搜索引擎的标题+摘要+链接 (不提取详情)

降级3 (全部不可用):
  返回 {"posts": [], "error": "...", "fallback_used": "rule_based"}
  Agent 知道数据来源降级，会在回复中标注
```

### 5.4 依赖与集成方式

XHS-Downloader 已 clone 到 `/Users/xinyiji/Desktop/XHS-Downloader`。

**方案：作为 pip 可编辑安装的本地包引用**

```bash
cd /Users/xinyiji/Desktop/XHS-Downloader
pip install -e .  # 或 uv pip install -e .
```

然后 NailFlow 中直接 import：

```python
from source.application import XHS
```

**不需要 TUI/CLI 部分**，只使用 `source/application/app.py` 和 `source/module/` 的提取逻辑。

**Cookie 配置**：

```yaml
# config.yaml
nail_xiaohongshu:
  enabled: true
  cookie: "$XHS_COOKIE"       # 从浏览器开发者工具获取
  search_delay_ms: 6000       # 每个请求之间的延迟
  search_engine: "bing"       # bing / google / duckduckgo
```

### 5.5 新增/修改文件

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `tools/nail/xiaohongshu_search.py` | 工具实现：搜索 → 提取 → 聚合 |
| 新增 | `tools/nail/xhs_client.py` | 封装 XHS-Downloader XHS 类 + 搜索引擎查询 |
| 修改 | `router_config.py` | `XIAOHONGSHU_SEARCH = CHAT` 能力声明 |
| 修改 | `nail_config.py` `_NAIL_TOOL_META` | 注册到工具列表 |
| 修改 | `nail_dev.py` `_TOOL_REGISTRY` | 开发工具注册 |
| 修改 | `config.yaml` `tools` | 注册 xiaohongshu_search_tool 到 nail_ops 组 |
| 修改 | `agents/lead_agent/prompt.py` | ops prompt 加入小红书搜索指引 |

---

## 六、Agent Prompt 调整

### 6.1 ops 页面模式前缀更新

在 `_NAIL_PAGE_MODE_PREFIX["ops"]` 末尾增加小红书工具的使用指引：

```
运营 Agent 工作流：
  trend_query_tool → trend_discovery_tool → ops_analysis_tool → action_proposal_tool

外部数据补充：
  在做趋势分析时，可调用 xiaohongshu_search_tool 查询小红书上的美甲趋势，
  与内部 ops_signals 数据交叉验证。发现小红书热门但店内未覆盖的款式时，
  应在分析报告中标注 "外部趋势" 并建议引入。

  调用建议：
  - 用户问"最近流行什么" → 同时调用 trend_query_tool + xiaohongshu_search_tool
  - 用户问"某款式情况" → 调用 xiaohongshu_search_tool(keyword="该款式")
  - 关键词提取：从用户问题中提取核心词，如"猫眼"、"法式"、"穿戴甲"
```

### 6.2 ops 角色前缀更新

在 `_NAIL_ROLE_PREFIX["ops"]` 中更新工具引导：

```
可以在飞书中与你双向对话。你也可以主动在预定时间发起分析（定时早报）。
```

---

## 七、文件总览

### 新增文件 (6个)

| 文件 | 行数估计 | 职责 |
|------|---------|------|
| `tools/nail/ops_channel/feishu_monitor.py` | ~350 | WebSocket 连接 + 事件循环 + 消息分发 |
| `tools/nail/ops_channel/feishu_session.py` | ~60 | feishu_sessions 表 CRUD |
| `tools/nail/ops_channel/feishu_reply.py` | ~80 | 飞书 Open API 回复/发送消息 |
| `tools/nail/xiaohongshu_search.py` | ~200 | 搜索工具 @tool 实现 |
| `tools/nail/xhs_client.py` | ~100 | XHS-Downloader 封装 + 搜索引擎查询 |

### 修改文件 (8个)

| 文件 | 改动量 | 说明 |
|------|-------|------|
| `base.py` | +15行 | feishu_sessions 表 DDL |
| `app.py` | +30行 | lifespan 启动/关闭 FeishuMonitor |
| `ops_scheduler.py` | +40行 | proactive_chat 注册 |
| `ops_runner.py` | +60行 | `_run_proactive_chat()` |
| `router_config.py` | +3行 | xiaohongshu_search 能力声明 |
| `nail_config.py` | +8行 | 工具元数据注册 |
| `nail_dev.py` | +5行 | 开发注册表 |
| `prompt.py` | +15行 | ops agent prompt 更新 |
| `config.yaml` | +40行 | feishu + xiaohongshu + proactive_chats 配置 |

### 前端修改 (1个)

| 文件 | 改动量 | 说明 |
|------|-------|------|
| `ops-channel-settings-page.tsx` | +60行 | proactive_chats 配置 UI |

---

## 八、自审清单

- [x] 无 TBD / TODO 占位符
- [x] 三段设计一致：FeishuMonitor / proactive_chat / xiaohongshu_search 都复用 LangGraph Thread + OpsScheduler
- [x] 范围聚焦：飞书双向通信 + 定时主动聊天 + 小红书搜索，不涉及微信/钉钉等其他通道
- [x] 降级路径明确：飞书有重连机制、XHS 有三层降级
- [x] 无模糊需求：每个工具的参数和返回值结构已定义

---

*设计完成，待用户审阅后进入实施计划阶段。*
