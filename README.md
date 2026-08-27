# nailflow — 美甲 AI 试戴与智能运营

> 美团黑客松「美甲 AI 试戴与智能运营」赛题参赛作品
---

## 解决的核心问题

美甲行业长期存在两个未被技术解决的关键矛盾：

| 痛点 | 现状 | nailflow 方案 |
|------|------|--------------|
| **试戴靠想象** | 用户到店前无法看到真实效果，决策依赖脑补 | AI 在手图上做局部 inpaint，保留手部自然细节，只改指甲区域 |
| **运营靠经验** | 门店运营缺乏数据驱动，不知道什么款在火、什么款该推 | 多 Agent 自动分析收藏/搜索/订单信号，生成可执行营销方案 |

---

## 产品演示

### 三端角色矩阵

```
👤 用户端（user）    AI 试戴 → 款式推荐 → 偏好记忆
📊 运营端（ops）     趋势洞察 → 方案生成 → 人工确认执行

```

### 核心功能一览

**用户端 — AI 试戴**
- 上传手图 + 款式图，6 步 AI 工作流自动完成试戴
- MediaPipe 手部关键点检测 → 甲面椭圆 Mask 生成
- 视觉 LLM 款式理解（颜色 / 甲型 / 纹理 / 饰品 / 渐变 / 猫眼等 10 种质地）
- 智能 Prompt 构建（正负向模板 + 动态反词 + RAG 增强）
- 字节 Seedream / 阿里 Wan2.7 双后端生图，支持 mock 降级
- 5 维度质量评估（边界 / 肤色 / 光照 / 款式相似度 / 自然感）

**运营端 — 智能运营**
- 实时聚合运营信号（save / order / click / search）
- LLM 趋势洞察 + 冷热款分析 + 可执行营销建议
- ActionProposal 人工确认机制，所有敏感操作需审批
- 运营记忆系统，历史营销反馈持续学习
- 客服工具，回复标注信息来源

---

## 技术架构

```
┌──────────────────────────────────────────────────────────────┐
│                   Next.js 16 Frontend                        │
│  tryon │ dashboard │ tools │ warehouse │ community │ data    │
│  10+ nail 组件 · SSE 流式思考链 · shadcn/ui · TanStack Query │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTP + SSE
┌───────────────────────────▼──────────────────────────────────┐
│                   FastAPI Gateway (:8001)                     │
│        JWT (nail_role)  ·  CSRF  ·  CORS  ·  19 路由         │
└───────────────────────────┬──────────────────────────────────┘
                            │ AgentContext(role, user_id, ...)
┌───────────────────────────▼──────────────────────────────────┐
│              nailflow LangGraph Runtime                       │
│                                                              │
│  Lead Agent（唯一入口）                                       │
│  ├─ nail_role 注入 → 工具组权限过滤                           │
│  ├─ nail_page_mode 注入 → 页面级工具二次过滤                   │
│  ├─ 模型 4 级优先级链：运行时 → Agent绑定 → DB默认 → 配置文件  │
│  └─ 18 层中间件栈（记忆/摘要/沙箱/澄清...）                    │
│                                                              │
│  工具层（21 个 @tool 装饰的函数）:                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ nail (15): hand_detect · nail_mask · style_understanding │
│  │   prompt_builder · image_generation · unified_tryon     │
│  │   quality_check · preference_rag · image_search         │
│  │   nail_style_recommend · nail_consult · knowledge_retrieval │
│  │   query_rewrite · trend_query · nail_run_query          │
│  │   user_pref_analytics                                  │
│  ├─────────────────────────────────────────────────────┤    │
│  │ nail_ops (5): trend_discovery · ops_analysis            │
│  │   customer_service · action_proposal · xiaohongshu_search │
│  ├─────────────────────────────────────────────────────┤    │
│  │ nail_dev (1): evaluation                                │
│  └─────────────────────────────────────────────────────┘    │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                       数据层                                  │
│  SQLite (9 张表)  ·  ChromaDB (3 个向量集合)  ·  本地文件存储  │
│  APScheduler 定时任务  ·  飞书 IM 集成  ·  小红书爬虫          │
└──────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| Agent 编排 | **LangGraph** | SSE 流式思考链，Checkpoint 持久化 |
| 后端 | **FastAPI + uvicorn** | 异步，内嵌 LangGraph 运行时 |
| 手部检测 | **MediaPipe Tasks** | HandLandmarker，21 个关键点定位 |
| 向量检索 | **ChromaDB + Chinese-CLIP** | 进程内向量库，甲面局部化 embedding |
| 关系数据库 | **SQLite** | 9 张表，零配置 |
| 定时任务 | **APScheduler** | 每日趋势报告自动生成 |
| 鉴权 | **PyJWT + bcrypt** | nail_role 写入 JWT payload |
| 前端框架 | **Next.js 16 + React 19** | App Router，TypeScript |
| UI 组件 | **shadcn/ui + Tailwind CSS** | 47 个 Radix UI 组件 |
| 服务端状态 | **TanStack Query** | 自动缓存/失效/重取 |
| LLM 接入 | **多厂商兼容 OpenAI 协议** | 千问 / DeepSeek / 豆包 / Kimi / 自定义 |

---

## 黑客松亮点

### 1. 多 Agent 编排 — 21 个工具、三层权限、两种过滤维度

不是简单的"调一个 API"，而是真正实现了多 Agent 协作：

- **双层工具过滤**：`nail_role`（用户身份）决定基础权限组，`nail_page_mode`（当前页面）做二次收缩。user 在 ops 页面也只能用 nail 工具，防止权限泄露
- **18 层中间件栈**：记忆注入 → 沙箱隔离 → 上下文压缩 → 图片预处理 → 不确定性澄清，全部可插拔
- **工具调用全链路日志**：每次调用记录输入/输出/耗时/思考链，可追溯可审计

### 2. 甲面局部化多模态 RAG

常规向量检索直接对整个款式图做 embedding，手和背景噪声严重。我们实现了：

- **甲面裁剪**：先 hand_detect 定位指甲 bounding box，只裁剪甲面区域
- **Masked View**：弱化背景，聚焦指甲内容
- **文本融合**：Chinese-CLIP 图像向量 + 款式标签文本向量加权融合
- **MMR 重排序**：平衡相关性和多样性，避免"全是猫眼"

三个 ChromaDB 集合支撑不同场景：`nail_styles`（款式检索）、`user_preferences`（个性化推荐）、`nail_knowledge`（知识问答）

### 3. 精准的 Prompt 工程 — 不只是"帮我画个美甲"

`unified_tryon_tool` 实现了**逐指分析 + 分层 Prompt 构建**：

- VLM 逐指分析（拇指到小指，每指独立款式描述）
- 动态负向提示词：奶牛纹自动追加"not round dots, pattern MUST be irregular organic blotches like Holstein cow hide"
- 图案锚定字典（`PATTERN_ANCHORS`）：12 种图案类型各有专属描述锚点，防止生图模型跑偏
- 硬约束注入："Edit ONLY the fingernail regions. Preserve original hand skin tone, wrinkles, joints, shadows, background"

### 4. 三端权限贯穿四层

nail_role 不是简单的 if-else，而是从**数据库 → JWT → Agent 工具过滤 → 前端路由守卫**全程贯通：

```python
# 后端 Agent 层
_ROLE_GROUPS = {"user": ["nail"], "ops": ["nail", "nail_ops"], "dev": ["nail", "nail_ops", "nail_dev"]}

# 前端路由层
if (!canAccess(nailRole, "ops")) return <PermissionDenied />
```

四个页面各自独立守卫，侧边导航栏按权限动态显示/隐藏菜单项。

### 5. 运行时模型热配置

不同于写死模型名称，我们实现了完整的运行时配置体系：

- **4 级模型优先级链**：运行时参数 → Agent DB 绑定 → DB 工具默认 → config.yaml 降级
- **工具级模型覆盖**：`quality_check` 可以用视觉模型、`ops_analysis` 用推理模型，互不干扰
- **多厂商兼容**：千问/DeepSeek/豆包/Kimi/自定义 OpenAI 兼容接口，UI 可视化增删改
- **热切换**：配置变更立即生效，无需重启


### 6. ActionProposal 人工确认闭环

运营 Agent 可以分析趋势、生成营销方案，但**所有敏感操作必须人类审批**：

```
trend_query → trend_discovery → ops_analysis → action_proposal (status=pending)
                                                      ↓
                                         人工在 Dashboard 确认/拒绝
                                                      ↓
                                         写入 ops_memory 作为历史学习
```

### 8. 完整的工程化实践

- **优雅降级**：生图 API 未配置时自动 mock；LLM 不可用时工具降级为规则引擎
- **幂等初始化**：`init_nail_tables()`、`seed_nail_users()`、`init_nail_styles()` 全部支持重复执行
- **11 个运维脚本**：数据种子、爬虫、索引审计、数据迁移、端到端安全验证
- **配置热重载**：config.yaml 修改后自动检测并重载，无需重启
- **原子写入**：配置 API 写回 YAML 时先写临时文件再 rename，防止写坏

---

## 快速启动

### 前置要求

- Python ≥ 3.12 + [uv](https://docs.astral.sh/uv/)
- Node.js ≥ 20 + pnpm
- 至少一个 LLM API Key

### 1. 克隆并配置

```bash
git clone https://github.com/your-org/hackathon-meituan-ai.git
cd hackathon-meituan-ai
cp .env.example .env   # 编辑填入 API Key
```

### 2. 安装依赖

```bash
# 后端
cd backend && uv sync && uv pip install mediapipe chromadb apscheduler pillow httpx

# 前端
cd ../frontend && pnpm install
```

### 3. 初始化数据

```bash
cd backend
python -c "from packages.harness.nailflow.tools.nail.base import init_nail_tables; init_nail_tables()"
python scripts/seed_nail_users.py
uv run python scripts/init_nail_styles.py          # 款式向量索引
uv run python scripts/fetch_seed_nail_assets.py    # 知识库种子数据
```

### 4. 启动

```bash
# 终端 1 — 后端 (:8001)
cd backend && uv run python -m uvicorn app.gateway.app:app --port 8001 --reload

# 终端 2 — 前端 (:3000)
cd frontend && pnpm dev
```

### 5. 登录验证

打开 `http://localhost:3000`，使用以下测试账号：

| 邮箱 | 密码 | 角色 | 可访问页面 |
|------|------|------|-----------|
| `user@nailflow.dev` | `nail123456` | 用户 | 试戴 · 款式库 · 社区 |
| `ops@nailflow.dev` | `nail123456` | 运营 | + 运营看板 · 数据查询 |
| `dev@nailflow.dev` | `nail123456` | 开发 | + 工具管理 · 模型配置 |

---

## 项目结构

```
hackathon-meituan-ai/
├── CLAUDE.md                        # Claude 开发指南（架构细节+编码规范）
├── README.md                        # 本文件
├── ARCHITECTURE.md                  # 架构设计文档
├── config.yaml                      # 主配置（模型/工具/沙箱/渠道）
│
├── backend/                         # Python 后端
│   ├── app/gateway/
│   │   ├── routers/                 # 19 个 API 路由
│   │   │   ├── nail_ops.py          # 试戴业务 + 运营看板 API
│   │   │   ├── nail_config.py       # 模型/工具/渠道运行时配置 API
│   │   │   ├── auth.py              # JWT 登录/注册
│   │   │   └── models.py            # 模型列表（DB + config.yaml 合并）
│   │   ├── auth/                    # JWT 签发与验证（nail_role）
│   │   └── app.py                   # FastAPI 入口（lifespan 自动初始化）
│   ├── packages/harness/nailflow/
│   │   ├── agents/lead_agent/       # 主 Agent（角色注入 + 工具过滤）
│   │   │   ├── agent.py             # 模型优先级链 + 工具组过滤 + 调用日志
│   │   │   └── prompt.py            # 角色/页面模式 System Prompt 模板
│   │   └── tools/nail/              # 21 个美甲专属工具
│   │       ├── hand_detect.py       # MediaPipe 手部关键点检测
│   │       ├── nail_mask.py         # 椭圆 Mask 生成
│   │       ├── style_understanding.py  # VLM 款式属性提取
│   │       ├── prompt_builder.py    # 分层 Prompt 构建（含 RAG 增强）
│   │       ├── image_generation.py  # Seedream/Wan2.7 双后端生图
│   │       ├── unified_tryon.py     # 一步式逐指试戴（核心）
│   │       ├── quality_check.py     # VLM 5 维度质量评估
│   │       ├── image_search.py      # 以图搜图
│   │       ├── nail_style_recommend.py  # 多模态推荐（MMR 重排序）
│   │       ├── nail_consult.py      # 统一咨询入口（意图路由）
│   │       ├── knowledge_retrieval.py   # 美甲知识库 RAG
│   │       ├── query_rewrite.py     # 规则查询改写
│   │       ├── preference_rag.py    # 用户偏好信号管理
│   │       ├── user_pref_analytics.py   # 用户偏好聚合分析
│   │       ├── trend_query.py       # 运营信号 SQL 聚合
│   │       ├── trend_discovery.py   # LLM 趋势洞察
│   │       ├── ops_analysis.py      # 营销方案生成
│   │       ├── customer_service.py  # 客服机器人
│   │       ├── action_proposal.py   # 方案提案入库（待审批）
│   │       ├── nail_run_query.py    # 执行历史查询
│   │       ├── xiaohongshu_search.py    # 小红书爬虫
│   │       ├── evaluation.py        # 赛题自动评分
│   │       ├── embedding.py         # Chinese-CLIP 甲面局部化向量
│   │       └── base.py              # DB 连接 · 路径常量 · 表初始化
│   └── scripts/                     # 11 个运维脚本
│
├── frontend/                        # Next.js 16 前端
│   └── src/
│       ├── app/workspace/nail/      # 6 个 nailflow 页面
│       │   ├── tryon/               # AI 试戴
│       │   ├── dashboard/           # 运营看板
│       │   ├── tools/               # 工具管理（意图链模拟）
│       │   ├── warehouse/           # 素材库
│       │   ├── community/           # 社区动态
│       │   └── data/                # 自然语言查数据
│       ├── components/nail/         # 11 个美甲组件
│       ├── components/workspace/
│       │   ├── nail-nav.tsx         # 侧边导航（权限过滤）
│       │   └── settings/            # 设置弹窗（含模型配置 Tab）
│       ├── core/nail-models/        # 模型配置 hooks + API
│       ├── core/nail-chat/          # Agent 对话 hooks（SSE 流）
│       └── lib/nail-auth.ts         # 前端权限工具
│
├── agents/                          # Agent 提示词资产
│   ├── prompts/                     # tryon / ops / evaluation 三套 System Prompt
│   └── schemas/                     # 评分结果 JSON Schema
│
└── data/                            # 运行时数据（gitignored）
    ├── nailflow.db                  # SQLite（9 张表）
    ├── uploads/                     # 用户上传图片
    ├── results/                     # 生成结果图
    ├── chroma/                      # ChromaDB 持久化
    └── mock/ops_signals.sql         # 运营信号 mock 数据
```

---

## API 概览

### 美甲业务

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/nail/dashboard?days=7` | 运营看板数据 |
| GET | `/api/nail/proposals?status=pending` | 方案列表 |
| POST | `/api/nail/proposals/{id}/confirm` | 确认/拒绝方案 |
| GET | `/api/nail/image?path=...` | 静态图片服务 |

### 运行时配置

| 方法 | 路径 | 说明 |
|------|------|------|
| CRUD | `/api/nail/config/models` | 模型配置管理 |
| GET/PUT | `/api/nail/config/agents` | Agent 模型绑定 |
| GET/PUT | `/api/nail/config/tools/{name}` | 工具开关/模型覆盖 |
| GET/PUT | `/api/nail/config/ops-channel` | 运营渠道配置 |
| GET/PUT | `/api/nail/config/feishu-chat` | 飞书集成配置 |

### Agent 运行

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/threads` | 创建对话线程 |
| POST | `/api/v1/threads/{id}/runs/stream` | SSE 流式运行 Agent |
| GET | `/api/models` | 可用模型列表（DB + config.yaml 合并去重） |

---

## 赛题评分对照

| 评分维度 | 权重 | nailflow 实现 | 关键证据 |
|---------|------|-------------|---------|
| 完整性 | 30 | 试戴全链路 6 步 + 运营闭环 4 步 + 3 类异常降级 | `unified_tryon_tool` 一步串联 + `action_proposal` 确认流程 |
| 应用效果 | 25 | inpaint 局部生图 + 质量 5 维度评估 + 肤色/光照保持 | 正负向 Prompt 硬约束 + VLM 质量检查 |
| 创新性 | 20 | 21 个工具多 Agent 编排 + 甲面局部化 RAG + 自评反馈闭环 | 双层权限过滤 + Chinese-CLIP 多模态向量 + EvaluationAgent |
| 商业价值 | 15 | ActionProposal 确认机制 + 运营记忆持续学习 + 小红书外部趋势 | `ops_memory` 表 + `xiaohongshu_search_tool` |
| 硬约束 | 10 | mock 降级保链路不断 + 每个工具 LLM→规则降级 + 工具调用日志 | `is_mock` 标记 + `_is_bare_nail_result` 重试 |

---

## 数据库设计

9 张 SQLite 表覆盖业务全链路：

| 表 | 用途 |
|---|------|
| `nail_runs` | Agent 执行记录（意图/角色/状态/耗时） |
| `nail_assets` | 图片资产路径（手图/款式图/mask/结果图） |
| `ops_signals` | 运营行为信号（save/order/click/search，带时间戳） |
| `action_proposals` | 运营方案提案（pending→approved/rejected，需人工确认） |
| `evaluation_results` | 赛题评分结果（5 维度分项 + 扣分原因 + 开发建议） |
| `ops_memory` | 运营历史记忆（营销反馈/风险记录，LLM 检索增强） |
| `nail_model_configs` | 用户自定义 LLM 模型（多厂商兼容） |
| `nail_agent_configs` | Agent 模型绑定（main_agent/tool_default） |
| `nail_tool_overrides` | 工具级模型覆盖 + 开关 + 页面启用 |

3 个 ChromaDB 向量集合：

| 集合 | 用途 | 嵌入方式 |
|------|------|---------|
| `nail_styles` | 款式语义检索 | Chinese-CLIP 图像+文本融合 |
| `user_preferences` | 用户偏好向量 | 历史交互款式向量加权平均 |
| `nail_knowledge` | 美甲知识库 | Chinese-CLIP 文本嵌入 |

---

## 开发指南

详细的开发规范、架构说明和常见问题请参阅 [CLAUDE.md](CLAUDE.md)。

### 添加新工具

1. 在 `backend/packages/harness/nailflow/tools/nail/` 创建 `@tool` 装饰的函数
2. 在 `config.yaml` 注册工具名和权限组（`nail` / `nail_ops` / `nail_dev`）
3. （可选）在 `nail_config.py` 的 `_NAIL_TOOL_META` 添加元信息供前端展示

### 添加新页面

1. 在 `frontend/src/app/workspace/nail/` 创建页面
2. 在 `nail-nav.tsx` 添加导航项（含 `requiredRole`）
3. 页面顶部加 `canAccess()` 权限守卫

---

## 提示词资产

| 文件 | 用途 |
|------|------|
| `agents/prompts/tryon_agent_prompt.md` | 试戴 Agent（3 步严格流程，禁止额外工具调用） |
| `agents/prompts/ops_agent_prompt.md` | 运营 Agent（检索策略 + 记忆系统 + 营销手段 + 人工确认） |
| `agents/prompts/evaluation_agent_prompt.md` | 评分 Agent（5 维度评分标准 + 扣分细则 + Demo 话术生成） |
| `agents/schemas/evaluation_result.schema.json` | 评分结果 JSON Schema |

---

## License

本项目为美团黑客松参赛作品，基于 LangGraph 自主搭建的多 Agent 编排框架。

---

*最后更新：2026-06-07*
