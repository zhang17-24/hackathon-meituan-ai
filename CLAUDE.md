# NailFlow — CLAUDE.md

> 给 Claude 的项目说明书。阅读此文件可以理解 NailFlow 的架构、约定和开发原则，直接开始高质量编码。

---

## 一、项目是什么

**NailFlow** 是美团黑客松"美甲 AI 试戴与智能运营"赛题的产品原型，基于 **DeerFlow**（字节开源的 LangGraph 多 Agent 框架）二次开发。

核心目标：
- **用户端**：上传手图 + 款式图 → AI 在指甲区域做局部 inpaint → 返回真实试戴效果图
- **运营端**：分析收藏/订单信号 → 生成运营方案 → 人工确认后记录执行
- **开发端**：EvaluationAgent 按赛题评分标准自动打分，反推下一步开发任务

**三端权限**（nail_role）：
```
user  → 只能试戴、推荐、查爆款
ops   → 以上 + 运营分析、方案生成、ActionProposal 确认
dev   → 以上 + EvaluationAgent 自评、工具单测、完整日志
```

---

## 二、项目根目录一眼看懂

```
hackathon-meituan-ai/
├── CLAUDE.md                   ← 本文件（Claude 开发指南）
├── README.md                   ← 项目概述（给人看）
├── ARCHITECTURE.md             ← 架构设计文档
├── config.yaml                 ← DeerFlow 配置（模型/工具/沙箱，gitignore）
├── .env                        ← 环境变量（API key，gitignore）
│
├── backend/                    ← Python 后端（FastAPI + LangGraph）
│   ├── app/gateway/
│   │   ├── routers/            ← 18 个路由文件（nail_ops.py, nail_config.py 等）
│   │   ├── auth/               ← JWT 鉴权（nail_role 签发）
│   │   ├── authz.py            ← @require_auth 装饰器
│   │   └── app.py              ← FastAPI 主应用（lifespan 注册）
│   └── packages/harness/deerflow/
│       ├── agents/lead_agent/  ← 主 Agent 工厂（nail_role 注入点）
│       └── tools/nail/         ← 13 个美甲专属工具（核心业务逻辑）
│
├── frontend/                   ← Next.js 16 前端
│   └── src/
│       ├── app/workspace/nail/ ← 四端页面（tryon/dashboard/evaluation/tools）
│       ├── components/nail/    ← 6 个美甲专属 React 组件
│       ├── components/workspace/
│       │   ├── nail-nav.tsx    ← 侧边 NailFlow 导航（权限过滤）
│       │   └── settings/       ← 设置弹窗（含模型配置 Tab）
│       ├── core/nail-models/   ← 模型配置 API hooks（React Query）
│       └── lib/nail-auth.ts    ← 前端权限工具函数
│
├── data/                       ← 运行时数据（gitignore）
│   ├── uploads/                ← 用户上传图片
│   ├── results/                ← 生成的 mask + 试戴结果图
│   ├── chroma/                 ← ChromaDB 持久化
│   ├── nailflow.db             ← SQLite 数据库（9 张表）
│   └── mock/
│       └── ops_signals.sql     ← 运营信号 mock 数据
│
├── agents/                     ← Agent 提示词和评分 Schema
│   ├── prompts/                ← 3 个 Agent Markdown 提示词
│   └── schemas/evaluation_result.schema.json
│
└── docs/superpowers/specs/
    └── 2026-05-29-nailflow-system-design.md  ← 完整系统设计文档
```

---

## 三、技术栈速查

| 层 | 技术 | 版本 | 说明 |
|----|------|------|------|
| Agent 编排 | DeerFlow + LangGraph | 0.1.0 | 主框架，SSE 流式思考链 |
| 后端 | FastAPI | 0.115+ | 异步，内嵌 LangGraph 运行时 |
| 包管理 | uv | latest | 后端依赖管理，比 pip 快 |
| LLM | 字节 Doubao/Volcengine | - | `VOLCENGINE_API_KEY` |
| 生图 | 字节生图 API（inpaint） | - | `NAIL_IMAGE_API_KEY` + `NAIL_IMAGE_API_URL` |
| 手部检测 | MediaPipe Tasks | 0.10+ | `HandLandmarker` Task API（非旧版 `mp.solutions`） |
| 向量库 | ChromaDB | 1.5.9+ | 进程内，默认嵌入函数（all-MiniLM-L6-v2） |
| 关系 DB | SQLite | built-in | `data/nailflow.db`，`contextmanager get_db()` |
| 定时任务 | APScheduler | 3.x | 每日 09:00 触发趋势分析 |
| 鉴权 | PyJWT + bcrypt | - | nail_role 写入 JWT payload |
| 前端 | Next.js + React | 16 / 19 | App Router，TypeScript |
| 包管理 | pnpm | latest | 前端依赖管理 |
| UI | shadcn/ui + Tailwind | 4.x | 47 个 Radix UI 组件 |
| 状态管理 | React Query (TanStack) | 5.x | 服务端状态；本地状态用 useState |
| LangGraph SDK | @langchain/langgraph-sdk | 1.5.3+ | 前端发起 thread/run |

---

## 四、开发环境启动

```bash
# 1. 后端依赖（第一次）
cd backend
uv sync
uv pip install mediapipe chromadb apscheduler pillow httpx

# 2. 数据库初始化（第一次，backend/ 目录下执行）
python -c "from packages.harness.deerflow.tools.nail.base import init_nail_tables; init_nail_tables()"
# 导入 mock 运营数据（可选）
sqlite3 ../data/nailflow.db < ../data/mock/ops_signals.sql
# 创建测试账号
python scripts/seed_nail_users.py   # 密码统一 nail123456

# 3. 配置 config.yaml（取消注释一个 models 条目，填入 API key）
# 4. 配置 .env（填入真实 API key）

# 5. 启动服务
# 终端 1：后端（:8001）
cd backend && uv run python -m uvicorn app.gateway.app:app --port 8001 --reload

# 终端 2：前端（默认 :3000，也可指定 :3001）
cd frontend && pnpm dev
```

> **注意**：`init_nail_tables()` 必须在 `backend/` 目录下运行，否则 `data/nailflow.db` 会建在错误路径。
> app.py lifespan 启动时会自动幂等调用，正常重启无需手动跑。

**测试账号**（seed 之后有效）：

| 邮箱 | 密码 | nail_role | 可访问路由 |
|------|------|-----------|-----------|
| user@nailflow.dev | nail123456 | user | `/workspace/nail/tryon` |
| ops@nailflow.dev | nail123456 | ops | + `/workspace/nail/dashboard` |
| dev@nailflow.dev | nail123456 | dev | + `/workspace/nail/evaluation`, `/workspace/nail/tools` |

---

## 五、架构核心：nail_role 贯穿四层

nail_role 是整个系统最重要的概念，从数据库到前端界面全程贯穿。

### 5.1 数据库层（`backend/app/gateway/auth/models.py`）

```python
class User(BaseModel):
    nail_role: Literal["user", "ops", "dev"] = Field(default="user")
```

### 5.2 JWT 层（`backend/app/gateway/auth/jwt.py`）

```python
payload = {
    "sub": str(user.id),
    "email": user.email,
    "nail_role": user.nail_role,  # 写入 token
}
```

### 5.3 Agent 层（`backend/packages/harness/deerflow/agents/lead_agent/agent.py`）

```python
nail_role = cfg.get("nail_role", "user")
_ROLE_GROUPS = {
    "user": ["nail"],
    "ops":  ["nail", "nail_ops"],
    "dev":  ["nail", "nail_ops", "nail_dev"],
}
nail_groups = _ROLE_GROUPS.get(nail_role, ["nail"])
tools = get_available_tools(groups=nail_groups, ...)
```

**模型优先级链**（在同一文件）：
```python
# 1. 请求体中的 model_name（用户手动选择）
# 2. nail_agent_configs["main_agent"]（DB 中的 Agent 绑定）
# 3. config.yaml 第一个 model
```

### 5.4 前端层（`frontend/src/lib/nail-auth.ts`）

```typescript
export function canAccess(userRole: NailRole, required: NailRole): boolean {
  const levels: Record<NailRole, number> = { user: 1, ops: 2, dev: 3 };
  return (levels[userRole] ?? 0) >= (levels[required] ?? 0);
}
// 使用：if (!canAccess(nailRole, "ops")) return <div>无权限</div>;
```

---

## 六、工具系统：13 个 nail 工具

所有工具在 `backend/packages/harness/deerflow/tools/nail/` 下，通过 `config.yaml` 的 `group` 字段注册。

### 6.1 工具组权限

| group | 工具 | 权限 |
|-------|------|------|
| `nail` | hand_detect, nail_mask, style_understanding, prompt_builder, image_generation, quality_check, preference_rag, trend_query | user + ops + dev |
| `nail_ops` | trend_discovery, ops_analysis, customer_service, action_proposal | ops + dev |
| `nail_dev` | evaluation | dev only |

### 6.2 工具 config.yaml 注册格式

```yaml
tools:
  - name: hand_detect          # 工具函数名（必须与 @tool 函数名一致）
    group: nail                # 权限组
    use: deerflow.tools.nail.hand_detect:hand_detect_tool  # Python 路径:对象名
```

### 6.3 工具模型优先级链

每个 LLM 工具在调用 `create_chat_model()` 时遵循以下优先级：
```
1. nail_tool_overrides[tool_name]    ← DB 中的工具专属模型覆盖
2. nail_agent_configs["tool_default"] ← DB 中的工具默认模型
3. nail_agent_configs["main_agent"]   ← 主 Agent 绑定模型
4. config.yaml 第一个模型
```

代码模式：
```python
from .base import get_tool_model
from deerflow.models import create_chat_model

# 在工具函数内
_tool_model = get_tool_model("your_tool_name")  # 可能返回 None
model = create_chat_model(name=_tool_model, thinking_enabled=False, attach_tracing=False)
```

### 6.4 新建工具的标准结构

```python
# backend/packages/harness/deerflow/tools/nail/your_tool.py
import json, logging
from langchain.tools import tool
from .base import get_db, get_tool_model
from deerflow.models import create_chat_model

logger = logging.getLogger(__name__)

@tool
def your_tool_name(param1: str, param2: str = "") -> str:
    """工具的功能描述（LLM 会读这里来决定是否调用）。

    Args:
        param1: 参数说明
        param2: 可选参数

    Returns:
        JSON 字符串，字段：result_field / error
    """
    try:
        # 使用 DB 配置的模型（有降级）
        _model = get_tool_model("your_tool_name")
        model = create_chat_model(name=_model, thinking_enabled=False, attach_tracing=False)
        # 主逻辑
        result = model.invoke(...)
        return json.dumps({"result_field": result}, ensure_ascii=False)
    except Exception as e:
        logger.error("YourTool failed: %s", e)
        # 降级：始终返回同结构的 JSON，不抛异常
        return json.dumps({"result_field": None, "error": str(e)})
```

**注册到 config.yaml**（在 nail 工具块末尾添加）：
```yaml
  - name: your_tool_name
    group: nail          # 或 nail_ops / nail_dev
    use: deerflow.tools.nail.your_tool:your_tool_name
```

---

## 七、数据库操作规范

### 7.1 get_db() 是上下文管理器，必须用 with

```python
from packages.harness.deerflow.tools.nail.base import get_db

# ✅ 正确
with get_db() as conn:
    rows = conn.execute("SELECT * FROM ops_signals WHERE ...").fetchall()

# ❌ 错误——会泄漏连接
conn = get_db()
rows = conn.execute("...").fetchall()
conn.close()
```

### 7.2 九张表说明

```sql
-- 业务数据
nail_runs           — 每次 Agent 执行记录（intent/status/nail_role）
nail_assets         — 图片资产（手图/mask/结果图的路径）
ops_signals         — 运营信号（click/save/order/search）
action_proposals    — 运营方案提案（pending→approved/rejected）
evaluation_results  — 评分结果（total_score/rubric/issues/tasks）
ops_memory          — 运营历史记忆（marketing/feedback/risk）

-- 用户自定义配置（新增，支持 UI 配置）
nail_model_configs  — 用户添加的 LLM 模型（千问/DeepSeek/豆包/Kimi/自定义）
nail_agent_configs  — Agent 模型绑定（main_agent/tool_default）
nail_tool_overrides — 工具级模型覆盖（tool_name → model_name）
```

### 7.3 模型配置辅助函数

```python
from packages.harness.deerflow.tools.nail.base import get_tool_model

# 获取工具绑定的模型（按优先级链）
model_name = get_tool_model("style_understanding")  # str | None
```

### 7.4 表初始化（幂等）

```python
from packages.harness.deerflow.tools.nail.base import init_nail_tables
init_nail_tables()  # 安全多次调用，IF NOT EXISTS
# app.py lifespan 已自动调用，无需手动调用
```

### 7.5 路径常量

```python
from packages.harness.deerflow.tools.nail.base import UPLOADS_DIR, RESULTS_DIR, DB_PATH
# 均为 Path 对象，从环境变量读取，有合理默认值
# UPLOADS_DIR = Path(os.getenv("NAIL_UPLOADS_DIR", "data/uploads"))
# RESULTS_DIR = Path(os.getenv("NAIL_RESULTS_DIR", "data/results"))
# DB_PATH     = Path(os.getenv("NAIL_DB_PATH", "data/nailflow.db"))
```

---

## 八、后端 API 路由清单

### 8.1 美甲业务 API（nail_ops.py）

```
POST  /api/nail/proposals/{id}/confirm   — 确认/拒绝运营方案
GET   /api/nail/proposals?status=pending — 方案列表
GET   /api/nail/dashboard?days=7         — 运营看板数据
GET   /api/nail/image?path=...           — 静态图片服务
```

### 8.2 NailFlow 配置 API（nail_config.py）

```
# 模型 CRUD
GET    /api/nail/config/models           — 列出用户配置的模型
POST   /api/nail/config/models           — 新增模型
PUT    /api/nail/config/models/{name}    — 更新模型
DELETE /api/nail/config/models/{name}    — 删除模型

# Agent 绑定
GET    /api/nail/config/agents           — 获取 main_agent/tool_default 绑定
PUT    /api/nail/config/agents           — 更新绑定

# 工具管理
GET    /api/nail/config/tools            — 列出全部工具（NailFlow+内置）
PUT    /api/nail/config/tools/{name}     — 更新工具开关/模型覆盖
```

### 8.3 模型 API（models.py，已扩展）

```
GET   /api/models                        — 返回 DB 用户模型 + config.yaml 静态模型
                                           DB 模型优先，同名跳过静态
```

### 8.4 认证 API（auth.py）

```
POST  /api/auth/login                    — 登录（返回 JWT，含 nail_role）
POST  /api/auth/register                 — 注册（nail_role 默认 "user"）
GET   /api/auth/me                       — 当前用户信息
POST  /api/auth/refresh                  — 刷新 token
POST  /api/auth/logout                   — 登出
```

### 8.5 添加新路由的标准方式

```python
# backend/app/gateway/routers/your_router.py
from app.gateway.authz import require_auth

router = APIRouter(prefix="/api/nail", tags=["nail"])

@router.get("/something")
@require_auth
async def your_endpoint(request: Request):
    user = request.state.user
    nail_role = user.nail_role
    ...
```

在 `app.py` 注册：
```python
from app.gateway.routers.your_router import router as your_router
app.include_router(your_router)
```

---

## 九、后端开发原则

### 9.1 文件修改前必须先 Read

用 Read 工具读取文件后再 Edit，不凭记忆猜测代码内容。DeerFlow 代码量大，很多函数有微妙的参数或副作用。

### 9.2 每个工具必须有降级路径

```python
try:
    # 主逻辑（可能依赖 LLM/外部 API）
    model = create_chat_model(...)
    result = model.invoke(...)
except Exception as e:
    logger.warning("ToolName LLM fallback: %s", e)
    # 规则降级，返回合理默认值，不抛异常
    result = default_result
```

### 9.3 工具返回值结构必须一致

成功和失败路径的 JSON key 集合要相同。前端和 Agent 按固定字段解析，字段缺失会静默 bug。

```python
# ✅ 成功时
return json.dumps({"proposal_id": "xxx", "status": "pending", "title": "...", "message": "..."})
# ✅ 失败时（字段相同）
return json.dumps({"proposal_id": "", "status": "failed", "title": "", "message": f"失败: {e}", "error": str(e)})

# ❌ 不一致（失败时少字段）
return json.dumps({"error": str(e)})
```

### 9.4 DeerFlow 的 create_chat_model 调用规范

```python
from deerflow.models import create_chat_model

# ✅ 在 nail 工具内部（非 lead_agent）
model = create_chat_model(thinking_enabled=False, attach_tracing=False)

# attach_tracing=False 是必须的！
# lead_agent 在 graph root 统一挂 tracing，工具内重复挂会产生重复 span
```

### 9.5 Python 路径注意事项

工具文件内的相对导入：
```python
from .base import get_db, RESULTS_DIR  # 同包内用相对导入

# 数据库路径相对于工作目录（hackathon-meituan-ai/）
# 后端从 backend/ 启动，NAIL_DB_PATH=./data/nailflow.db 
# 实际文件在 backend/data/nailflow.db
```

---

## 十、前端架构与目录

### 10.1 组件/模块分工

```
frontend/src/
├── app/workspace/nail/       ← 四个页面（路由级）
│   ├── tryon/page.tsx        ← 用户端试戴页面
│   ├── dashboard/page.tsx    ← 运营端看板
│   ├── evaluation/page.tsx   ← 开发端自评
│   └── tools/page.tsx        ← 工具管理页面
│
├── components/nail/          ← 美甲专属 React 组件
│   ├── image-uploader.tsx    ← 双图上传区（手图+款式图）
│   ├── progress-steps.tsx    ← 6 步试戴流程进度条
│   ├── result-panel.tsx      ← 试戴结果展示+评分
│   ├── tool-card.tsx         ← 工具卡片（带开关+模型选择）
│   ├── model-selector-inline.tsx  ← 工具级模型选择下拉
│   └── nail-model-picker.tsx ← 对话页面头部模型选择器
│
├── components/workspace/settings/  ← 设置弹窗
│   ├── settings-dialog.tsx   ← 含 "模型配置" Tab
│   ├── model-settings-page.tsx     ← 模型列表+Agent绑定
│   └── model-form-dialog.tsx ← 新建/编辑模型表单
│
├── core/nail-models/         ← 模型配置业务逻辑
│   ├── types.ts              ← NailModelConfig, AgentConfigs, ToolInfo
│   ├── api.ts                ← fetch 封装（自动带 CSRF）
│   └── hooks.ts              ← React Query hooks
│
└── lib/nail-auth.ts          ← canAccess() 权限检查
```

### 10.2 获取当前用户的 nail_role

```typescript
"use client";
import { useAuth } from "@/core/auth/AuthProvider";
import type { NailRole } from "@/lib/nail-auth";

export default function SomePage() {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role as NailRole ?? "user";
  // ...
}
```

### 10.3 发起 Agent SSE 流式运行

```typescript
// 1. 创建 thread
const thread = await fetch("/api/v1/threads", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: "{}",
}).then(r => r.json());
const threadId = thread.thread_id ?? thread.id;

// 2. 发起 stream run（nail_role 从当前用户获取）
const runRes = await fetch(`/api/v1/threads/${threadId}/runs/stream`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    input: {
      messages: [{ role: "user", content: "用户的问题或指令" }],
    },
    config: {
      configurable: {
        nail_role: nailRole,       // ← 必须传，否则默认 user 权限
        model_name: selectedModel, // ← 可选，用户选择的模型
      },
    },
  }),
});

// 3. 读取 SSE 流
const reader = runRes.body!.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  const chunk = decoder.decode(value);
  for (const line of chunk.split("\n")) {
    if (!line.startsWith("data: ")) continue;
    try {
      const data = JSON.parse(line.slice(6));
      // data.type: "message_chunk" | "tool_call" | "tool_result" | "done"
    } catch { /* 忽略非 JSON 行 */ }
  }
}
```

### 10.4 使用模型配置 hooks

```typescript
import { useNailModels, useAgentConfigs, useTools } from "@/core/nail-models";
import { useModels } from "@/core/models/hooks";

// 用户配置的模型（DB）
const { data: nailModels } = useNailModels();

// 所有可用模型（DB + config.yaml，去重合并）
const { models } = useModels();

// Agent 绑定（main_agent, tool_default）
const { data: agentConfigs } = useAgentConfigs();

// 工具列表（NailFlow 13 个 + 内置 5 个）
const { data: tools } = useTools();
```

### 10.5 权限守卫模式

```typescript
// 页面级守卫（早期返回）
if (!canAccess(nailRole, "ops")) {
  return (
    <div className="flex h-full items-center justify-center text-muted-foreground">
      ⚠️ 需要运营或开发权限才能访问此页面
    </div>
  );
}

// 组件级守卫（条件渲染）
{canAccess(nailRole, "dev") && <DevOnlyPanel />}
```

### 10.6 样式规范

- 使用 Tailwind 工具类，不写 CSS 文件
- 颜色主题变量从 `tailwind.config.ts` 中的 CSS variables 取
- `text-muted-foreground`：次要文字颜色
- `bg-card` / `bg-background`：卡片/页面背景
- NailFlow 品牌色：`pink-500`（用户端主色）、`blue-600`（开发端）、`green-500`（确认/通过）

### 10.7 调用 NailFlow 专属 API

```typescript
import { listNailModels, createNailModel, updateAgentConfigs } from "@/core/nail-models/api";

// 推荐用 hooks（自动缓存/失效）
const { mutateAsync: createModel } = useCreateNailModel();
await createModel({ name: "qwen-vl", display_name: "千问 VL", ... });

// 直接调用（表单提交等场景）
const res = await updateAgentConfigs({ main_agent: "qwen-max", tool_default: "qwen-plus" });
```

---

## 十一、关键业务流程代码参考

### 11.1 试戴完整工具链调用顺序

```
hand_detect_tool(image_path)
  → nail_mask_tool(image_path, nail_bboxes_json)
  → style_understanding_tool(style_image_path, user_description?)
  → prompt_builder_tool(style_analysis_json, user_request?)
  → image_generation_tool(hand_image_path, mask_path, prompt_json)
  → quality_check_tool(original_hand_path, result_path, style_summary_zh?)
```

每步输出 JSON，下一步读前一步的输出字段。Agent 自动串联。

### 11.2 运营方案生成→确认流程

```
TrendQueryTool (ops_signals 聚合)
  → TrendDiscoveryTool (LLM 洞察报告)
  → OpsAnalysisTool (2-3 条营销方案)
  → ActionProposalTool (写 action_proposals 表，status=pending)
  → 人工在 /workspace/nail/dashboard 点"确认"
  → POST /api/nail/proposals/{id}/confirm {status: "approved"}
  → 写入 ops_memory 作为历史记录
```

### 11.3 EvaluationAgent 自评

```
evaluation_tool(run_summary, run_id?)
  → LLM 按赛题 rubric 打分
  → 存 evaluation_results 表
  → 返回 total_score / blocking_issues / next_dev_tasks
```

---

## 十二、常见问题与陷阱

### Q: 工具导入失败 "No module named 'packages'"

在 `backend/` 目录外运行时需要设置绝对路径：
```python
import sys, os
sys.path.insert(0, '/path/to/hackathon-meituan-ai/backend')
os.chdir('/path/to/hackathon-meituan-ai')  # data/ 路径相对于此
```

### Q: SQLite "no such table" 错误

最常见原因：`init_nail_tables()` 在错误目录运行，建了错误路径的 DB。
- 后端始终从 `backend/` 目录启动
- `NAIL_DB_PATH=./data/nailflow.db` → 实际是 `backend/data/nailflow.db`
- app.py lifespan 已自动调用 `init_nail_tables()`，正常重启后会自动修复

### Q: MediaPipe 无法检测到手部

- 图片需要完整的手背，不能只有手指
- 需要正面拍摄，光线充足
- 避免背景颜色与肤色过于相近
- 工具已有友好中文提示，告知用户重拍条件

### Q: 生图 API 未配置时的行为

`image_generation_tool` 检测到 `NAIL_IMAGE_API_KEY` 为空时，自动进入 mock 模式：
- 把原手图复制到 results/ 目录作为"结果图"
- 返回 `{"is_mock": true, "result_path": "..."}`
- 前端显示黄色提示条

### Q: config.yaml `models: null` 启动报错

把 `models:` 改为 `models: []`（空列表），不要删除该字段。

### Q: 前端 nail_role 取不到

`useAuth()` 返回的 `user` 对象类型是 DeerFlow 原始的 `User`，没有 `nail_role` 字段类型声明，但运行时 JWT payload 里有这个字段。用 `(user as any)?.nail_role` 读取。

### Q: 工具页面空白（500 错误）

确认 `nail_tool_overrides` 表已创建：
```bash
cd backend
python -c "from packages.harness.deerflow.tools.nail.base import init_nail_tables; init_nail_tables()"
```

### Q: config.yaml 中工具名和函数名不一致

DeerFlow 会 warning 但仍使用函数的 `.name` 属性。必须保持：
```yaml
- name: hand_detect  # ← 这里的 name
```
与 Python 中 `@tool` 修饰的函数名（`hand_detect_tool`）的 `.name` 属性一致。

---

## 十三、DeerFlow 框架关键点

### 13.1 LangGraph 运行时

DeerFlow 使用 LangGraph 的 Checkpoint + Thread 模型：
- `Thread` = 一次对话（含历史消息）
- `Run` = 在 Thread 上执行一次 Agent
- SSE stream = Agent 运行时的实时事件流

前端通过 `/api/v1/threads/{id}/runs/stream` 获取流式输出。

### 13.2 Agent 中间件栈（执行顺序）

Lead agent 有一套中间件，按顺序执行：
1. `ThreadDataMiddleware` — 每线程隔离目录
2. `UploadsMiddleware` — 把上传图片 URL 注入 Agent 上下文
3. `SandboxMiddleware` — 分配沙箱资源
4. `SummarizationMiddleware` — 上下文压缩
5. `TodoListMiddleware` — 任务跟踪
6. `TitleMiddleware` — 对话标题生成
7. `MemoryMiddleware` — 注入长期记忆
8. `ViewImageMiddleware` — 图像数据注入
9. `ClarificationMiddleware` — 不确定时向用户提问（**必须最后**）

### 13.3 工具的 `use:` 路径格式

```yaml
use: deerflow.tools.nail.hand_detect:hand_detect_tool
# 格式：Python 模块路径:对象名
# 注意：模块路径从 backend/ 目录开始（uv 将 packages/harness 安装为可导入包）
```

### 13.4 Skill 与 Tool 的区别

- **Tool（工具）**：Python 函数，用 `@tool` 装饰，在 config.yaml 注册
- **Skill（技能）**：Markdown 文件，描述给 Agent 看的操作流程，存在 skills/ 目录
- NailFlow 当前主要用 Tool，Skill 暂未使用

---

## 十四、赛题评分权重（开发优先级依据）

开发功能时，优先做分值高的：

| 评分维度 | 分值 | 最影响分数的功能 |
|---------|------|---------------|
| 完整性 | 30 | 试戴全链路跑通、异常处理 |
| 应用效果 | 25 | 生图质量、边界清晰度 |
| 创新性 | 20 | 多 Agent 编排、RAG 推荐、自评反馈 |
| 商业价值 | 15 | ActionProposal 流程、运营转化指标 |
| 硬约束 | 10 | 生成 <30s、工具 <3s |

`evaluation_tool` 能直接告诉你哪里扣分、怎么改，用 dev 账号随时跑。

---

## 十五、文件修改高频场景速查

| 要做什么 | 改哪个文件 |
|---------|-----------|
| 添加新的 nail 工具 | `tools/nail/your_tool.py` + `config.yaml` |
| 修改 AI 系统提示词 | `agents/lead_agent/prompt.py` 的 `_NAIL_ROLE_PREFIX` |
| 添加新 API 接口 | `app/gateway/routers/nail_ops.py` |
| 添加模型配置接口 | `app/gateway/routers/nail_config.py` |
| 修改三端路由守卫 | `app/workspace/nail/*/page.tsx` 开头的 `canAccess()` |
| 修改运营看板数据 | `app/gateway/routers/nail_ops.py` 的 `get_dashboard()` |
| 修改试戴页面 UI | `app/workspace/nail/tryon/page.tsx` |
| 修改工具管理页面 | `app/workspace/nail/tools/page.tsx` |
| 修改侧边导航 | `components/workspace/nail-nav.tsx` |
| 修改 DB 表结构 | `tools/nail/base.py` 的 `init_nail_tables()` |
| 修改权限角色 | `auth/models.py` + `agents/lead_agent/agent.py` 的 `_ROLE_GROUPS` |
| 修改生图 prompt 模板 | `tools/nail/prompt_builder.py` 的 `_POS_TEMPLATE` / `_NEG_PROMPT` |
| 修改设置弹窗 | `components/workspace/settings/settings-dialog.tsx` |
| 修改模型表单 | `components/workspace/settings/model-form-dialog.tsx` |
| 修改模型列表页 | `components/workspace/settings/model-settings-page.tsx` |

---

*最后更新：2026-05-29*
