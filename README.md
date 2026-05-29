# NailFlow — 美甲 AI 试戴与智能运营

> 美团黑客松赛题原型 · 基于 DeerFlow（字节多 Agent 框架）二次开发  
> **多 Agent 编排 + AI 试戴 + 智能运营 + 三端权限 + 自动评分**

---

## 产品概述

NailFlow 解决了美甲行业的两个核心矛盾：

| 问题 | NailFlow 解决方案 |
|------|-----------------|
| 用户无法"所见即所得"，试色靠想象 | AI 在真实手图上 inpaint，生成毫米级精准的试戴效果图 |
| 运营无法"实时感知"爆款趋势 | 多 Agent 自动分析收藏/搜索/订单信号，生成可执行营销方案 |

### 三端角色

```
👤 用户端 (user)    → AI 试戴 → 款式推荐 → 门店预约
📊 运营端 (ops)     → 趋势分析 → 方案生成 → 人工确认执行  
🔧 开发端 (dev)     → 工具管理 → 模型配置 → 自动评分
```

---

## 功能特性

### 用户端试戴
- 📸 上传手图 + 款式图，6 步 AI 工作流自动完成试戴
- 🖐 MediaPipe 手部检测 + 精准甲面 Mask 生成
- 🎨 款式理解（颜色/甲型/纹理/饰品标签）
- ⚡ 智能 Prompt 构建 + 字节生图 API inpaint
- ✅ 自动质量评估（边界/肤色/光照/款式相似度）
- 💾 用户偏好 RAG 记忆（ChromaDB 向量检索）

### 运营端智能运营
- 📈 实时聚合运营信号（点击/收藏/订单/搜索）
- 🧠 LLM 趋势洞察 + 营销方案自动生成
- 📋 ActionProposal 人工确认机制（防止自动误操作）
- 📊 运营看板：方案状态追踪 + 历史效果记录
- 💬 客服工具：引用门店事实、价格、档期

### 开发端自评
- 🏆 EvaluationAgent 按赛题 5 维度自动打分（0-100）
- 🔍 识别扣分原因，推荐下一步开发任务（按评分收益排序）
- 🔧 工具管理：开关控制 + 工具级模型覆盖
- ⚙️ 设置中心：可视化配置模型（千问/DeepSeek/豆包/Kimi/自定义）

---

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                  Next.js 16 Frontend                │
│  用户端试戴  |  运营看板  |  工具管理  |  设置中心   │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────┐
│              FastAPI Gateway (:8001)                │
│  JWT Auth (nail_role)  |  CSRF  |  CORS             │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│           DeerFlow LangGraph Runtime                │
│  ┌─────────────────────────────────────────────┐   │
│  │              Lead Agent                     │   │
│  │  nail_role → 工具组权限过滤                  │   │
│  │  [nail] [nail_ops] [nail_dev]               │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  工具层（13 个 nail 工具）:                          │
│  hand_detect → nail_mask → style_understanding     │
│  prompt_builder → image_generation → quality_check  │
│  trend_query → trend_discovery → ops_analysis      │
│  action_proposal → preference_rag → evaluation     │
└─────────────────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                   数据层                            │
│  SQLite (nailflow.db)  |  ChromaDB (用户偏好)        │
│  data/uploads/         |  data/results/             │
└─────────────────────────────────────────────────────┘
```

### 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| Agent 编排 | DeerFlow + LangGraph | 0.1.0 |
| 后端 | FastAPI + uvicorn | 0.115+ |
| 手部检测 | MediaPipe Tasks API | 0.10+ |
| 向量库 | ChromaDB（进程内） | 1.5.9+ |
| 关系数据库 | SQLite（9 张表） | built-in |
| 定时任务 | APScheduler | 3.x |
| 前端框架 | Next.js + React | 16 / 19 |
| UI 组件 | shadcn/ui + Tailwind CSS | 4.x |
| 服务端状态 | TanStack Query (React Query) | 5.x |
| 前端 Agent SDK | @langchain/langgraph-sdk | 1.5.3+ |

---

## 快速启动

### 前置要求

- Python ≥ 3.12（推荐用 [uv](https://docs.astral.sh/uv/) 管理）
- Node.js ≥ 20 + pnpm
- 至少一个 LLM API Key（千问/DeepSeek/豆包/Kimi 均可）

### 1. 克隆项目

```bash
git clone https://github.com/your-org/hackathon-meituan-ai.git
cd hackathon-meituan-ai
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入真实值：

```bash
# LLM 接入（必填，任选其一）
OPENAI_API_KEY=your_llm_api_key
OPENAI_BASE_URL=https://your-llm-endpoint/v1

# 生图 API（选填，不填则自动进入 mock 模式）
NAIL_IMAGE_API_KEY=your_image_api_key
NAIL_IMAGE_API_URL=https://your-image-api/inpaint

# 安全（生产时务必修改）
JWT_SECRET_KEY=nailflow-hackathon-secret-2026
```

### 3. 配置 LLM 模型

编辑 `config.yaml`，取消注释并填入一个模型：

```yaml
models:
  - name: your-model-name        # 自定义名称
    model: your-model-id         # 模型 ID
    api_key: $OPENAI_API_KEY      # 引用环境变量
    base_url: $OPENAI_BASE_URL
    use_class: ChatOpenAI
```

> 也可以在启动后进入「设置 → 模型配置」通过 UI 配置，支持千问、DeepSeek、豆包、Kimi。

### 4. 安装依赖

```bash
# 后端
cd backend
uv sync
uv pip install mediapipe chromadb apscheduler pillow httpx

# 前端
cd ../frontend
pnpm install
```

### 5. 初始化数据库 + 创建测试账号

```bash
# 必须在 backend/ 目录下执行
cd backend
python -c "from packages.harness.deerflow.tools.nail.base import init_nail_tables; init_nail_tables()"
python scripts/seed_nail_users.py
```

### 6. 启动服务

**终端 1：后端**
```bash
cd backend
uv run python -m uvicorn app.gateway.app:app --port 8001 --reload
```

**终端 2：前端**
```bash
cd frontend
pnpm dev
```

打开 `http://localhost:3000`，用以下账号登录：

| 邮箱 | 密码 | 角色 | 可访问页面 |
|------|------|------|----------|
| user@nailflow.dev | nail123456 | 用户 | AI 试戴 |
| ops@nailflow.dev | nail123456 | 运营 | 以上 + 运营看板 |
| dev@nailflow.dev | nail123456 | 开发 | 以上 + 工具管理 + 自评 |

---

## 项目目录结构

```
hackathon-meituan-ai/
├── CLAUDE.md                    # Claude 开发指南（详细架构说明）
├── README.md                    # 本文件
├── ARCHITECTURE.md              # 系统架构设计文档
├── config.yaml                  # DeerFlow 模型/工具/沙箱配置
├── .env                         # 环境变量（gitignored）
│
├── backend/                     # Python 后端
│   ├── app/gateway/
│   │   ├── routers/
│   │   │   ├── nail_ops.py      # 试戴业务 API (/api/nail/*)
│   │   │   ├── nail_config.py   # 模型/工具配置 API (/api/nail/config/*)
│   │   │   ├── auth.py          # 登录/注册/JWT
│   │   │   ├── models.py        # 模型列表（DB + config.yaml 合并）
│   │   │   └── ...              # 15 个 DeerFlow 标准路由
│   │   ├── auth/                # JWT 鉴权（nail_role 签发）
│   │   └── app.py               # FastAPI 主应用
│   └── packages/harness/deerflow/
│       ├── agents/lead_agent/   # 主 Agent（nail_role 权限注入）
│       └── tools/nail/          # 13 个美甲专属工具
│           ├── base.py          # DB 连接 + 9 张表 + get_tool_model()
│           ├── hand_detect.py   # 手部检测（MediaPipe Tasks）
│           ├── nail_mask.py     # 甲面 Mask 生成
│           ├── style_understanding.py  # 款式解析（LLM）
│           ├── prompt_builder.py       # 生图 Prompt 构建
│           ├── image_generation.py     # 生图调用（支持 mock）
│           ├── quality_check.py        # 质量评估（LLM）
│           ├── preference_rag.py       # 用户偏好检索（ChromaDB）
│           ├── trend_query.py          # 运营信号聚合
│           ├── trend_discovery.py      # 趋势洞察（LLM）
│           ├── ops_analysis.py         # 营销方案生成（LLM）
│           ├── customer_service.py     # 客服工具（LLM）
│           ├── action_proposal.py      # 方案提案入库
│           └── evaluation.py           # 赛题评分（LLM）
│
├── frontend/                    # Next.js 16 前端
│   └── src/
│       ├── app/workspace/nail/  # 四个 NailFlow 页面
│       │   ├── tryon/           # 用户端试戴
│       │   ├── dashboard/       # 运营看板
│       │   ├── evaluation/      # 开发自评
│       │   └── tools/           # 工具管理
│       ├── components/nail/     # 6 个美甲专属组件
│       ├── components/workspace/settings/  # 设置弹窗（含模型配置）
│       ├── core/nail-models/    # 模型配置业务逻辑（hooks + API）
│       └── lib/nail-auth.ts     # 权限检查工具函数
│
├── data/                        # 运行时数据（gitignored）
│   ├── nailflow.db              # SQLite 数据库
│   ├── uploads/                 # 用户上传的图片
│   ├── results/                 # 生成的试戴结果图
│   ├── chroma/                  # ChromaDB 持久化
│   └── mock/ops_signals.sql     # 运营信号 mock 数据
│
└── agents/                      # Agent 提示词资产
    ├── prompts/                 # 3 个 Agent Markdown 提示词
    └── schemas/                 # 评分结果 JSON Schema
```

---

## API 概览

### 美甲业务接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/nail/dashboard` | 运营看板数据 |
| GET | `/api/nail/proposals` | ActionProposal 列表 |
| POST | `/api/nail/proposals/{id}/confirm` | 确认/拒绝方案 |
| GET | `/api/nail/image` | 静态图片服务 |

### 配置接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/nail/config/models` | 列出用户配置的模型 |
| POST | `/api/nail/config/models` | 新增模型 |
| PUT | `/api/nail/config/models/{name}` | 更新模型 |
| DELETE | `/api/nail/config/models/{name}` | 删除模型 |
| GET/PUT | `/api/nail/config/agents` | Agent 模型绑定 |
| GET | `/api/nail/config/tools` | 工具列表（13+5） |
| PUT | `/api/nail/config/tools/{name}` | 更新工具开关/模型 |

### 标准 DeerFlow 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/threads` | 创建对话线程 |
| POST | `/api/v1/threads/{id}/runs/stream` | SSE 流式运行 Agent |
| GET | `/api/models` | 可用模型列表 |
| POST | `/api/auth/login` | 登录 |
| GET | `/health` | 健康检查 |

---

## 数据库设计

SQLite 数据库位于 `backend/data/nailflow.db`（相对于 `backend/` 目录），共 9 张表：

| 表名 | 用途 |
|------|------|
| `nail_runs` | Agent 执行记录 |
| `nail_assets` | 图片资产路径 |
| `ops_signals` | 运营行为信号 |
| `action_proposals` | 运营方案提案 |
| `evaluation_results` | 评分结果 |
| `ops_memory` | 运营历史记忆 |
| `nail_model_configs` | 用户配置的 LLM 模型 |
| `nail_agent_configs` | Agent 模型绑定配置 |
| `nail_tool_overrides` | 工具级模型覆盖配置 |

---

## 模型配置说明

NailFlow 支持三种方式配置模型，优先级从高到低：

1. **UI 配置**（推荐）：「设置 → 模型配置」，支持千问/DeepSeek/豆包/Kimi/自定义
2. **config.yaml**：静态配置，适合固定部署
3. **环境变量**：通过 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 配置默认模型

### 支持的模型提供商

| 提供商 | use_class | 参考 api_base |
|--------|-----------|--------------|
| 阿里云千问 | ChatOpenAI | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| DeepSeek | ChatOpenAI | `https://api.deepseek.com/v1` |
| 字节豆包 | ChatOpenAI | `https://ark.cn-beijing.volces.com/api/v3` |
| 月之暗面 Kimi | ChatOpenAI | `https://api.moonshot.cn/v1` |
| 自定义 | ChatOpenAI | 任何 OpenAI 兼容接口 |

---

## 赛题评分对照

| 评分维度 | 权重 | NailFlow 实现 |
|---------|------|-------------|
| 完整性 | 30% | 试戴全链路（6 步）+ 运营闭环 + 3 类异常处理 |
| 应用效果 | 25% | inpaint 局部生图 + 质量 5 维度评估 |
| 创新性 | 20% | DeerFlow 多 Agent + RAG 偏好 + 自评反馈 |
| 商业价值 | 15% | ActionProposal 确认机制 + 运营记忆 |
| 硬约束 | 10% | mock 模式保证不超时 + 三类失败降级 |

用 dev 账号访问「评分面板」，运行 EvaluationAgent 查看当前得分和改进建议。

---

## 开发指南

详细的开发规范、架构说明和常见问题请参阅 [CLAUDE.md](CLAUDE.md)。

### 添加新工具

1. 在 `backend/packages/harness/deerflow/tools/nail/` 创建工具文件
2. 在 `config.yaml` 注册工具和权限组
3. （可选）在 `backend/app/gateway/routers/nail_config.py` 的 `_NAIL_TOOL_META` 添加工具元信息供前端展示

### 添加新页面

1. 在 `frontend/src/app/workspace/nail/` 创建页面目录
2. 在 `frontend/src/components/workspace/nail-nav.tsx` 添加导航项
3. 设置 `requiredRole` 权限守卫

---

## 提示词资产

| 文件 | 用途 |
|------|------|
| [agents/prompts/tryon_agent_prompt.md](agents/prompts/tryon_agent_prompt.md) | 试戴 Agent 系统提示词 |
| [agents/prompts/ops_agent_prompt.md](agents/prompts/ops_agent_prompt.md) | 运营 Agent 系统提示词 |
| [agents/prompts/evaluation_agent_prompt.md](agents/prompts/evaluation_agent_prompt.md) | 评分 Agent 系统提示词 |
| [agents/schemas/evaluation_result.schema.json](agents/schemas/evaluation_result.schema.json) | 评分结果 JSON Schema |

---

## License

本项目为美团黑客松参赛作品，基于 [DeerFlow](https://github.com/bytedance/deer-flow) 二次开发。

---

*最后更新：2026-05-29*
