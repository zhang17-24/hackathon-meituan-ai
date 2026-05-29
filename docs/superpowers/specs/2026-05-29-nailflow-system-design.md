# NailFlow 系统设计文档

> 状态：设计中（持续更新）
> 日期：2026-05-29
> 作者：zhangkai169
> 黑客松截止：3 天

---

## 一、背景与目标

### 赛题

美团黑客松"美甲 AI 试戴与智能运营"——面向美甲消费者和门店运营商的双端（后扩展为三端）AI Agent 产品。

### 核心矛盾

- 用户无法"所见即所得"（试戴效果不真实）
- 运营无法"实时感知"（趋势和用户偏好无工具支撑）

### 交付目标（3 天内）

| 维度 | 要求 |
|---|---|
| 链路完整 | 每个环节真实调用，Demo 时全程无 mock |
| 体验完整 | 前端流畅、有加载状态、有异常处理 |
| 架构完整 | 代码结构清晰、每个 Agent 和工具都有实现 |

---

## 二、技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| Agent 编排 | DeerFlow (fork) + LangGraph | 现成多 Agent 全栈框架，SSE 流式思考链展示 |
| 运营 Agent 模式 | OpenClaw 记忆/检索模式（借鉴，不整体迁移） | 运营记忆、多轮检索、可执行动作设计成熟 |
| 前端 | Next.js (DeerFlow 原有) + Tailwind | 复用 DeerFlow Agent 工作台 UI |
| 后端 | Python FastAPI | DeerFlow 原有 |
| LLM | 字节系 LLM（与生图同平台）| 统一 API 调用 |
| 图像生成 | 字节生图 API（inpaint/mask edit）| 已验证效果 |
| 向量库 | ChromaDB（进程内，无需独立服务）| 轻量，适合黑客松 |
| 关系数据库 | SQLite（开发期）→ PostgreSQL（可选）| 零配置，快速迭代 |
| 定时任务 | APScheduler | 运营端定时看板生成 |
| 鉴权 | JWT（role claim）| 简单 RBAC，支持三端路由守卫 |

---

## 三、三端权限矩阵

```
角色        可用端              可用 Agent
────────────────────────────────────────────────────────────────
user        用户端              TryOnAgent / TrendAgent / PreferenceAgent
ops         用户端 + 运营端      以上 + OpsAnalysisAgent / CustomerServiceAgent
                               / TrendDiscoveryAgent / ActionProposalAgent
dev         三端全开            以上 + EvaluationAgent / DebugTraceAgent
```

---

## 四、整体架构

```
┌────────────────────────────────────────────────────────────────────┐
│                          前端 (Next.js)                             │
│                                                                    │
│  /login → JWT 解析 role → 路由守卫                                  │
│                                                                    │
│  用户端 /user/*          运营端 /ops/*          开发端 /dev/*        │
│  ├─ 试戴上传              ├─ 试戴工作台          ├─ 三端全视图         │
│  ├─ 偏好推荐              ├─ 运营看板            ├─ Agent 评分面板     │
│  └─ 款式发现              ├─ 客服对话            ├─ 完整日志 trace     │
│                          └─ ActionProposal      └─ 模型/prompt 切换  │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ JWT Bearer Token
┌──────────────────────────────▼─────────────────────────────────────┐
│                    FastAPI  —  Auth Middleware                      │
│                                                                    │
│  decode_jwt(token) → role: "user" | "ops" | "dev"                  │
│  route_guard: 每个 /api/* 端点标注 allowed_roles                    │
│  agent_guard: 构建 AgentContext 时注入 role，过滤可用 sub-agents      │
└───────────────────────────────┬────────────────────────────────────┘
                                │ AgentContext(role, user_id, ...)
┌───────────────────────────────▼────────────────────────────────────┐
│                     NailPlannerAgent（唯一主 Agent）                 │
│                                                                    │
│  role → ROLE_PROMPTS[role]        system prompt 切换               │
│  role → ROLE_MODELS[role]         可选：dev 端用更强模型             │
│  role → ALLOWED_SUBAGENTS[role]   sub-agent 白名单过滤              │
│                                                                    │
│  user:  [TryOnAgent, TrendAgent, PreferenceAgent]                  │
│  ops:   以上 + [OpsAnalysisAgent, CustomerServiceAgent,            │
│                 TrendDiscoveryAgent, ActionProposalAgent]           │
│  dev:   以上 + [EvaluationAgent, DebugTraceAgent]                  │
└────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼────────────────────────────────────┐
│                        共享数据层                                    │
│  SQLite（runs / assets / ops_signals / action_proposals）           │
│  ChromaDB（用户偏好图向量 + 款式标签向量）                             │
│  本地文件存储（手图 / mask / 试戴结果图）                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 五、用户端 Agent 链路

```
用户输入（手图 + 款式图/需求文字）
  │
  ▼
NailPlannerAgent（role=user/ops/dev）
  │  解析意图：试戴？推荐？查爆款？
  │
  ├──[试戴意图]──▶ TryOnAgent
  │                 1. HandDetectTool        检测手部姿态 + 指尖坐标
  │                 2. NailMaskTool          生成甲面 mask（SAM lite）
  │                 3. StyleUnderstandingTool 解析款式：颜色/纹理/饰品/甲型
  │                 4. PromptBuilderTool     ← 先根据图片内容+用户需求生成提示词
  │                    └─ 输入：手图描述 + 款式标签 + 用户需求
  │                       输出：正向 prompt + 反向 prompt（英文）
  │                 5. 字节生图 API          image + mask + prompt → 试戴图
  │                 6. TryOnQualityTool      甲面边界/肤色/光照评分
  │                 7. 输出：试戴图 + 中文解释 + 适合度评语
  │
  ├──[推荐意图]──▶ PreferenceAgent
  │                 1. 查 ChromaDB 用户偏好向量
  │                 2. 相似款式召回 top-5
  │                 3. 结合当前趋势重排序
  │                 4. 输出：推荐画廊 + 推荐理由
  │
  └──[爆款查询]──▶ TrendAgent
                    1. 查 ops_signals 表（点击/收藏/预约）
                    2. 7 日/30 日趋势聚合
                    3. 输出：本周爆款 top-10 + 趋势标签
```

### PromptBuilderTool 说明

这是关键节点，把图片理解结果和用户需求合成为生图模型的精确 prompt：

**正向模板：**
```
Edit only the fingernail regions inside the provided nail mask.
Preserve the original hand skin tone, wrinkles, joints, shadows,
background, camera angle, and lighting.
Apply the nail art style: {style_description}.
Photorealistic commercial beauty retouching, natural hand photo.
```

**反向模板：**
```
do not redraw the hand, do not change skin tone, no extra fingers,
no missing fingers, no deformed nails, no floating decorations,
no blurry cuticle, no color bleeding outside nail mask
```

---

## 六、运营端 + 开发端 Agent 链路

### 触发方式
- **手动**：运营/开发在对话框发起查询
- **定时**：APScheduler 每天 09:00 触发日报生成

```
NailPlannerAgent（role=ops/dev，同一个主 Agent，ops 系统提示词注入）
  │
  ├──[趋势分析]──▶ TrendDiscoveryAgent        OpenClaw 检索模式
  │                 读 ops_signals + 用户试戴记录
  │                 输出：爆款榜 + 滞销预警 + 搜索词热点
  │
  ├──[运营建议]──▶ OpsAnalysisAgent
  │                 输入：趋势数据 + 门店库存（mock）
  │                 记忆模式：历史营销反馈存 DB → 检索增强
  │                 输出：ActionProposal（套餐/限时/达人文案）
  │                       → 需人工确认才能"执行"（Mock API）
  │
  ├──[客服]──────▶ CustomerServiceAgent
  │                 多轮对话 + 门店知识库 RAG
  │                 回答必须标注信息来源（SOP / 趋势 / 用户偏好）
  │
  └──[评估]──────▶ EvaluationAgent（仅 dev 角色）
                    输入：本次 Run 的完整日志 + 原始图 + 结果图
                    输出：
                      - total_score: 0-100
                      - rubric_scores: 完整性/效果/创新性/商业价值/硬约束
                      - blocking_issues: 必须修复的问题
                      - next_dev_tasks: 下一步任务（按评分收益排序）
                      - demo_evidence: 答辩可展示证据
```

### 开发端额外能力

- 查看任意 Run 的完整 Agent 思考链（不过滤）
- 直接调用单个 tool 测试（HandDetect / PromptBuilder / QualityCheck）
- 切换主 Agent 的 system prompt 版本，对比效果
- EvaluationAgent 自动打分 + 生成下一步开发任务

---

## 七、数据模型

### SQLite 表结构

```sql
-- 一次 Agent 执行记录
runs
  id          TEXT  PK
  user_id     TEXT
  role        TEXT   -- "user" | "ops" | "dev"
  intent      TEXT   -- "tryon" | "recommend" | "trend" | "ops_query"
  status      TEXT   -- "running" | "done" | "failed"
  created_at  DATETIME

-- Agent 每一步的思考内容（运营端可查）
agent_thoughts
  id          INTEGER PK AUTOINCREMENT
  run_id      TEXT  FK→runs
  agent_name  TEXT   -- "TryOnAgent" | "OpsAnalysisAgent" | ...
  step        INTEGER
  thought     TEXT
  tool_call   TEXT   -- JSON，工具名+参数
  tool_result TEXT   -- JSON，工具返回
  created_at  DATETIME

-- 图片资产（手图/mask/结果图/款式图）
assets
  id          TEXT  PK
  run_id      TEXT  FK→runs
  type        TEXT   -- "hand" | "style" | "mask" | "result"
  file_path   TEXT
  created_at  DATETIME

-- 运营信号（点击/收藏/预约，用于趋势分析）
ops_signals
  id          INTEGER PK AUTOINCREMENT
  user_id     TEXT
  style_id    TEXT
  signal_type TEXT   -- "click" | "save" | "order" | "search"
  created_at  DATETIME

-- 运营动作提案（需人工确认）
action_proposals
  id           TEXT  PK
  run_id       TEXT  FK→runs
  title        TEXT
  content      TEXT   -- JSON，ActionProposal 完整内容
  status       TEXT   -- "pending" | "approved" | "rejected"
  created_at   DATETIME
  confirmed_at DATETIME NULL

-- 评估结果（dev 端）
evaluation_results
  id              TEXT  PK
  run_id          TEXT  FK→runs
  total_score     INTEGER
  rubric_scores   TEXT   -- JSON
  blocking_issues TEXT   -- JSON
  next_dev_tasks  TEXT   -- JSON
  demo_evidence   TEXT   -- JSON
  created_at      DATETIME
```

### ChromaDB 集合

```
collection: user_preferences
  document: 用户试戴过/收藏过的款式描述文本
  metadata: { user_id, style_id, colors, nail_type, created_at }
  embedding: 款式描述向量

collection: nail_styles
  document: 款式标签描述
  metadata: { style_id, name, price_range, tags }
  embedding: 款式语义向量（用于推荐召回）
```

---

## 八、目录结构

基于 DeerFlow fork，改造如下：

```
nailflow/
├── web/                          # Next.js 前端（DeerFlow 改造）
│   ├── app/
│   │   ├── (auth)/login/         # 登录页，JWT 获取
│   │   ├── user/                 # 用户端路由（role=user/ops/dev）
│   │   │   ├── tryon/            # 试戴上传 + 结果
│   │   │   ├── recommend/        # 偏好推荐画廊
│   │   │   └── trend/            # 爆款发现
│   │   ├── ops/                  # 运营端路由（role=ops/dev）
│   │   │   ├── dashboard/        # 运营看板
│   │   │   ├── chat/             # 运营对话 + 客服
│   │   │   └── proposals/        # ActionProposal 确认面板
│   │   └── dev/                  # 开发端路由（role=dev only）
│   │       ├── trace/            # 完整 Agent 思考链
│   │       ├── evaluation/       # EvaluationAgent 评分面板
│   │       └── tools/            # 单个 tool 调试
│   └── components/
│       ├── agent-stream/         # SSE 流式思考链展示（DeerFlow 复用）
│       ├── tryon-canvas/         # 手图上传 + mask 可视化
│       └── ops-dashboard/        # 运营看板图表
│
├── backend/                      # Python FastAPI
│   ├── api/
│   │   ├── auth.py               # JWT 签发 + 验证
│   │   ├── tryon.py              # /api/tryon 端点
│   │   ├── ops.py                # /api/ops/* 端点
│   │   └── dev.py                # /api/dev/* 端点
│   ├── agents/
│   │   ├── planner.py            # NailPlannerAgent（主 Agent，角色注入）
│   │   ├── tryon_agent.py        # TryOnAgent
│   │   ├── trend_agent.py        # TrendAgent
│   │   ├── preference_agent.py   # PreferenceAgent + ChromaDB
│   │   ├── ops_analysis.py       # OpsAnalysisAgent
│   │   ├── customer_service.py   # CustomerServiceAgent
│   │   ├── trend_discovery.py    # TrendDiscoveryAgent
│   │   ├── action_proposal.py    # ActionProposalAgent
│   │   └── evaluation.py         # EvaluationAgent（dev only）
│   ├── tools/
│   │   ├── hand_detect.py        # HandDetectTool（MediaPipe）
│   │   ├── nail_mask.py          # NailMaskTool（SAM lite）
│   │   ├── style_understanding.py # StyleUnderstandingTool
│   │   ├── prompt_builder.py     # PromptBuilderTool ← 关键
│   │   ├── image_generation.py   # 字节生图 API 封装
│   │   └── quality_check.py      # TryOnQualityTool
│   ├── memory/
│   │   ├── chroma_store.py       # ChromaDB 封装
│   │   └── ops_memory.py         # 运营记忆（OpenClaw 模式）
│   ├── scheduler/
│   │   └── ops_scheduler.py      # APScheduler 定时看板
│   ├── db/
│   │   ├── models.py             # SQLAlchemy 模型
│   │   └── migrations/           # 建表脚本
│   ├── config/
│   │   ├── roles.py              # ROLE_PROMPTS / ROLE_MODELS / ALLOWED_SUBAGENTS
│   │   └── settings.py           # 环境变量
│   └── main.py
│
├── data/
│   ├── mock/                     # mock 数据（门店/订单/库存）
│   ├── uploads/                  # 用户上传图片
│   └── results/                  # 生图结果
│
└── docs/
    └── superpowers/specs/
        └── 2026-05-29-nailflow-system-design.md
```

---

## 九、3 天开发顺序

**原则：最难的先做，风险前置，复用优先，末尾用 EvaluationAgent 自评驱动修复。**

---

### Day 1：地基 + 视觉核心链路

> 目标：字节生图 API 从头到尾跑通，其余全是壳

| 时段 | 任务 |
|---|---|
| 上午（4h） | Fork DeerFlow 清理骨架；建表；config/roles.py；JWT auth；前端 3 路由空壳 |
| 下午（4h） | hand_detect / nail_mask / style_understanding / prompt_builder / image_generation 5 个 tools |
| 晚上（2h） | TryOnAgent 串联 5 个 tools，接 /api/tryon，跑真实手图验证 |

**Day 1 验收**：输入手图 + 款式图 → 返回试戴结果图

---

### Day 2：完整用户链路 + 运营地基

> 目标：3 个用户端 Agent 全通，运营端核心 Agent 可对话

| 时段 | 任务 |
|---|---|
| 上午（4h） | quality_check tool；ChromaDB 封装；PreferenceAgent；TrendAgent；NailPlannerAgent（意图路由+角色注入） |
| 下午（4h） | mock 数据；OpsMemory；TrendDiscoveryAgent；OpsAnalysisAgent；CustomerServiceAgent；/api/ops/* 端点 |
| 晚上（2h） | 前端 tryon-canvas 组件；SSE agent-stream 复用 DeerFlow |

**Day 2 验收**：3 角色均可登录；运营端能生成并确认 ActionProposal

---

### Day 3：开发端 + 打磨 + 自评驱动修复

> 目标：全链路无崩溃，EvaluationAgent 打分 ≥ 75，Demo 脚本跑通

| 时段 | 任务 |
|---|---|
| 上午（4h） | EvaluationAgent；/api/dev/* 端点；前端 dev 三面板；异常处理补全 |
| 下午（3h） | APScheduler 定时任务；前端 ops dashboard（图表）；proposals 确认面板 |
| 傍晚（2h） | dev 账号跑完整 Demo → EvaluationAgent 自评 → 修复 blocking_issues |
| 晚上（1h） | Demo 脚本准备；README 一键启动命令；3 角色演示账号 |

---

### 风险与兜底

| 风险 | 兜底策略 |
|---|---|
| 字节生图 API 延迟 > 30s | Day 1 预渲染 3 组典型结果，Demo 可切"快速预览"模式 |
| MediaPipe 手部检测失败 | 降级为用户在前端手动框选甲面 |
| SAM mask 不准 | 降级为 bbox 矩形 mask，质量分低但链路不断 |
| DeerFlow fork 改造出 bug | 每天结束前 commit 干净基线，随时可回滚 |
| ChromaDB 向量质量差 | 用标签文本余弦相似度兜底，不依赖嵌入质量 |

---

> 状态：**实现计划已生成**
>
> 实现计划：[docs/superpowers/plans/2026-05-29-nailflow-implementation.md](../plans/2026-05-29-nailflow-implementation.md)
>
> *文档持续更新，每次设计对话后同步追加*
