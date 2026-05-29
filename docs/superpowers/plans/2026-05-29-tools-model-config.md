# NailFlow 工具管理 + 模型配置 + Agent 模型选择 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 NailFlow 中实现可视化模型配置（Settings tab）、工具管理页（侧边栏）和对话页模型快速切换，无需修改代码文件即可完成所有 AI 模型和工具的配置。

**Architecture:** 混合存储方案——用户自定义模型存 SQLite（nail_model_configs 等 3 张新表），启动时与 config.yaml 静态模型合并；三个前端入口（Settings/工具页/对话页）共用同一套后端 API。

**Tech Stack:** Python/FastAPI + SQLite（后端）、Next.js/React/TypeScript + TanStack Query（前端）、Tailwind CSS + shadcn/ui（样式）

---

## 文件变更地图

```
backend/packages/harness/deerflow/tools/nail/base.py   ← 新增3张表到 init_nail_tables()
backend/app/gateway/routers/nail_config.py             ← 新建：模型/Agent/工具 CRUD API
backend/app/gateway/routers/models.py                  ← 修改：合并 DB + config.yaml
backend/app/gateway/app.py                             ← 注册 nail_config_router

frontend/src/core/nail-models/types.ts                 ← 新建：类型定义
frontend/src/core/nail-models/api.ts                   ← 新建：API 调用
frontend/src/core/nail-models/hooks.ts                 ← 新建：React Query hooks
frontend/src/core/nail-models/index.ts                 ← 新建：re-export

frontend/src/components/workspace/settings/settings-dialog.tsx        ← 插入 models tab
frontend/src/components/workspace/settings/model-settings-page.tsx    ← 新建
frontend/src/components/workspace/settings/model-form-dialog.tsx      ← 新建

frontend/src/components/nail/nail-model-picker.tsx     ← 新建：对话页顶部选择器
frontend/src/components/nail/model-selector-inline.tsx ← 新建：工具卡片内嵌选择器
frontend/src/components/nail/tool-card.tsx             ← 新建：工具卡片

frontend/src/app/workspace/nail/tools/page.tsx         ← 新建：工具管理主页面
frontend/src/app/workspace/chats/[thread_id]/page.tsx  ← 修改：插入 NailModelPicker
frontend/src/components/workspace/nail-nav.tsx         ← 修改：添加 🔧 工具 导航项
```

---

## Phase 1：后端基础（DB + API）

### Task 1: 在 base.py 新增 3 张配置表

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/base.py`

- [ ] **Step 1: 读取 base.py 确认 init_nail_tables 位置**

```bash
cat /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/backend/packages/harness/deerflow/tools/nail/base.py
```

- [ ] **Step 2: 在 init_nail_tables() 的 executescript 中追加 3 张表**

找到 `executescript("""` 块，在最后一个 `CREATE TABLE` 之后追加：

```python
        CREATE TABLE IF NOT EXISTS nail_model_configs (
            id           TEXT PRIMARY KEY,
            name         TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            provider     TEXT NOT NULL,
            model_id     TEXT NOT NULL,
            api_key      TEXT,
            api_base     TEXT NOT NULL,
            use_class    TEXT NOT NULL,
            supports_vision   INTEGER DEFAULT 0,
            supports_thinking INTEGER DEFAULT 0,
            is_active    INTEGER DEFAULT 1,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS nail_agent_configs (
            config_key   TEXT PRIMARY KEY,
            model_name   TEXT NOT NULL,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS nail_tool_overrides (
            tool_name    TEXT PRIMARY KEY,
            model_name   TEXT,
            is_enabled   INTEGER DEFAULT 1,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        );
```

- [ ] **Step 3: 验证表创建**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/backend
python3 -c "
import sys, os; sys.path.insert(0, '.')
os.chdir('..')
from packages.harness.deerflow.tools.nail.base import init_nail_tables, get_db
init_nail_tables()
with get_db() as conn:
    tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
    for t in ['nail_model_configs','nail_agent_configs','nail_tool_overrides']:
        print(f'  {t}: {\"OK\" if t in tables else \"MISSING\"}')
"
```

期望：三张表全部输出 OK

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add backend/packages/harness/deerflow/tools/nail/base.py
git commit -m "feat(db): add nail_model_configs, nail_agent_configs, nail_tool_overrides tables"
```

---

### Task 2: 创建 nail_config.py 后端路由

**Files:**
- Create: `backend/app/gateway/routers/nail_config.py`

- [ ] **Step 1: 创建文件**

```python
# backend/app/gateway/routers/nail_config.py
"""NailFlow 配置 API：模型 CRUD、Agent 绑定、工具开关管理。"""
import logging
import uuid
from datetime import datetime, UTC
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.gateway.authz import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nail/config", tags=["nail-config"])


def _get_db():
    from packages.harness.deerflow.tools.nail.base import get_db
    return get_db()


# ─── Pydantic 模型 ──────────────────────────────────────────

class NailModelCreate(BaseModel):
    name: str
    display_name: str
    provider: str               # "qwen"|"deepseek"|"doubao"|"kimi"|"custom"
    model_id: str
    api_key: Optional[str] = None
    api_base: str
    use_class: str
    supports_vision: bool = False
    supports_thinking: bool = False

class NailModelUpdate(BaseModel):
    display_name: Optional[str] = None
    model_id: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    use_class: Optional[str] = None
    supports_vision: Optional[bool] = None
    supports_thinking: Optional[bool] = None
    is_active: Optional[bool] = None

class NailModelResponse(BaseModel):
    id: str
    name: str
    display_name: str
    provider: str
    model_id: str
    api_base: str
    use_class: str
    supports_vision: bool
    supports_thinking: bool
    is_active: bool
    created_at: str
    source: str = "db"   # "db" | "config"

class AgentConfigUpdate(BaseModel):
    main_agent: Optional[str] = None
    tool_default: Optional[str] = None

class ToolOverrideUpdate(BaseModel):
    model_name: Optional[str] = None
    is_enabled: Optional[bool] = None


# ─── 模型 CRUD ────────────────────────────────────────────

@router.get("/models")
@require_auth
async def list_nail_models(request: Request):
    """列出所有用户自定义模型（DB 中的）。"""
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, display_name, provider, model_id, api_base, use_class, "
            "supports_vision, supports_thinking, is_active, created_at "
            "FROM nail_model_configs ORDER BY created_at DESC"
        ).fetchall()
    models = [NailModelResponse(
        id=r["id"], name=r["name"], display_name=r["display_name"],
        provider=r["provider"], model_id=r["model_id"], api_base=r["api_base"],
        use_class=r["use_class"], supports_vision=bool(r["supports_vision"]),
        supports_thinking=bool(r["supports_thinking"]), is_active=bool(r["is_active"]),
        created_at=r["created_at"], source="db"
    ) for r in rows]
    return {"models": models}


@router.post("/models", status_code=201)
@require_auth
async def create_nail_model(body: NailModelCreate, request: Request):
    """创建新模型配置。"""
    model_id_gen = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    with _get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM nail_model_configs WHERE name = ?", (body.name,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"模型名称 '{body.name}' 已存在")
        conn.execute(
            "INSERT INTO nail_model_configs "
            "(id, name, display_name, provider, model_id, api_key, api_base, use_class, "
            "supports_vision, supports_thinking, is_active, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?)",
            (model_id_gen, body.name, body.display_name, body.provider, body.model_id,
             body.api_key, body.api_base, body.use_class,
             int(body.supports_vision), int(body.supports_thinking), now, now)
        )
        conn.commit()
    return {"id": model_id_gen, "name": body.name, "message": "创建成功"}


@router.put("/models/{model_name}")
@require_auth
async def update_nail_model(model_name: str, body: NailModelUpdate, request: Request):
    """更新模型配置。"""
    now = datetime.now(UTC).isoformat()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    # 布尔转整数
    for bool_field in ("supports_vision", "supports_thinking", "is_active"):
        if bool_field in updates:
            updates[bool_field] = int(updates[bool_field])
    updates["updated_at"] = now
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [model_name]
    with _get_db() as conn:
        result = conn.execute(
            f"UPDATE nail_model_configs SET {set_clause} WHERE name = ?", values
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"模型 '{model_name}' 不存在")
    return {"message": "更新成功"}


@router.delete("/models/{model_name}")
@require_auth
async def delete_nail_model(model_name: str, request: Request):
    """删除模型配置。"""
    with _get_db() as conn:
        result = conn.execute(
            "DELETE FROM nail_model_configs WHERE name = ?", (model_name,)
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"模型 '{model_name}' 不存在")
    return {"message": "删除成功"}


# ─── Agent 模型绑定 ──────────────────────────────────────

@router.get("/agents")
@require_auth
async def get_agent_configs(request: Request):
    """获取主 Agent 和工具默认模型绑定。"""
    with _get_db() as conn:
        rows = conn.execute(
            "SELECT config_key, model_name FROM nail_agent_configs"
        ).fetchall()
    result = {r["config_key"]: r["model_name"] for r in rows}
    return {
        "main_agent": result.get("main_agent"),
        "tool_default": result.get("tool_default"),
    }


@router.put("/agents")
@require_auth
async def update_agent_configs(body: AgentConfigUpdate, request: Request):
    """更新 Agent 模型绑定（upsert）。"""
    now = datetime.now(UTC).isoformat()
    with _get_db() as conn:
        if body.main_agent is not None:
            conn.execute(
                "INSERT OR REPLACE INTO nail_agent_configs (config_key, model_name, updated_at) "
                "VALUES ('main_agent', ?, ?)", (body.main_agent, now)
            )
        if body.tool_default is not None:
            conn.execute(
                "INSERT OR REPLACE INTO nail_agent_configs (config_key, model_name, updated_at) "
                "VALUES ('tool_default', ?, ?)", (body.tool_default, now)
            )
        conn.commit()
    return {"message": "更新成功"}


# ─── 工具管理 ─────────────────────────────────────────────

# 工具元数据（name, display_name, emoji, description, group, requires_llm, requires_vision）
_NAIL_TOOL_META = [
    ("hand_detect_tool",         "手部检测",   "🔍", "用 MediaPipe 识别手指位置和甲床 bbox",                "nail",     False, False),
    ("nail_mask_tool",           "甲面遮罩",   "✂️", "根据 bbox 生成甲面 mask PNG，白色=甲面",             "nail",     False, False),
    ("style_understanding_tool", "款式理解",   "🎨", "调用 LLM Vision 解析款式颜色/纹理/甲型",             "nail",     True,  True),
    ("prompt_builder_tool",      "提示词构建", "✍️", "将款式分析结果合成为生图 positive/negative prompt", "nail",     False, False),
    ("image_generation_tool",    "AI 生图",    "⚡", "调用字节生图 API 进行 inpaint 试戴生成",             "nail",     False, False),
    ("quality_check_tool",       "质量评分",   "✅", "双图对比评估试戴效果：边界/肤色/光照/款式",           "nail",     True,  True),
    ("preference_rag_tool",      "偏好记忆",   "💾", "ChromaDB 存储用户喜好款式，支持个性化推荐",           "nail",     False, False),
    ("trend_query_tool",         "趋势查询",   "📈", "查询近 N 天款式热度信号排行榜",                      "nail",     False, False),
    ("trend_discovery_tool",     "趋势洞察",   "🔥", "综合趋势数据，LLM 生成爆款洞察报告",                 "nail_ops", True,  False),
    ("ops_analysis_tool",        "运营方案",   "📋", "基于趋势和历史记忆生成可执行营销方案",               "nail_ops", True,  False),
    ("customer_service_tool",    "智能客服",   "💬", "多轮客服对话，回答预约/价格/售后问题",               "nail_ops", True,  False),
    ("action_proposal_tool",     "方案提案",   "🔔", "将运营方案写入 DB，等待人工确认后执行",              "nail_ops", False, False),
    ("evaluation_tool",          "自动评分",   "🏆", "按赛题评分标准对本次运行自动打分",                    "nail_dev", True,  False),
]

_BUILTIN_TOOL_META = [
    ("web_search",  "🌐", "网页搜索",  "DuckDuckGo 网页搜索，无需 API Key",    "web"),
    ("web_fetch",   "📥", "网页抓取",  "抓取并解析网页内容",                    "web"),
    ("file:read",   "📄", "文件读取",  "读取本地文件内容",                       "file"),
    ("file:write",  "💾", "文件写入",  "写入或创建本地文件",                     "file"),
    ("bash",        "🖥️", "命令执行",  "在沙箱中执行 bash 命令",                "bash"),
]


@router.get("/tools")
@require_auth
async def list_tools(request: Request):
    """列出所有工具（含开关状态和模型覆盖）。"""
    with _get_db() as conn:
        overrides = {
            r["tool_name"]: {"model_name": r["model_name"], "is_enabled": bool(r["is_enabled"])}
            for r in conn.execute(
                "SELECT tool_name, model_name, is_enabled FROM nail_tool_overrides"
            ).fetchall()
        }

    nail_tools = []
    for name, display_name, emoji, desc, group, req_llm, req_vision in _NAIL_TOOL_META:
        ov = overrides.get(name, {})
        nail_tools.append({
            "name": name, "display_name": display_name, "emoji": emoji,
            "description": desc, "group": group,
            "requires_llm": req_llm, "requires_vision": req_vision,
            "is_enabled": ov.get("is_enabled", True),
            "model_override": ov.get("model_name"),
        })

    builtin_tools = []
    for name, emoji, display_name, desc, group in _BUILTIN_TOOL_META:
        ov = overrides.get(name, {})
        builtin_tools.append({
            "name": name, "display_name": display_name, "emoji": emoji,
            "description": desc, "group": group,
            "requires_llm": False, "requires_vision": False,
            "is_enabled": ov.get("is_enabled", True),
            "model_override": None,
        })

    return {"nail_tools": nail_tools, "builtin_tools": builtin_tools}


@router.put("/tools/{tool_name}")
@require_auth
async def update_tool(tool_name: str, body: ToolOverrideUpdate, request: Request):
    """更新工具开关或模型绑定（upsert）。"""
    now = datetime.now(UTC).isoformat()
    with _get_db() as conn:
        existing = conn.execute(
            "SELECT tool_name FROM nail_tool_overrides WHERE tool_name = ?", (tool_name,)
        ).fetchone()
        if existing:
            updates = {}
            if body.model_name is not None:
                updates["model_name"] = body.model_name
            if body.is_enabled is not None:
                updates["is_enabled"] = int(body.is_enabled)
            if updates:
                updates["updated_at"] = now
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE nail_tool_overrides SET {set_clause} WHERE tool_name = ?",
                    list(updates.values()) + [tool_name]
                )
        else:
            conn.execute(
                "INSERT INTO nail_tool_overrides (tool_name, model_name, is_enabled, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (tool_name, body.model_name,
                 int(body.is_enabled) if body.is_enabled is not None else 1, now)
            )
        conn.commit()
    return {"message": "更新成功"}
```

- [ ] **Step 2: 验证文件语法**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/backend
python3 -c "import ast; ast.parse(open('app/gateway/routers/nail_config.py').read()); print('语法OK')"
```

期望：`语法OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add backend/app/gateway/routers/nail_config.py
git commit -m "feat(api): add nail_config router for model/agent/tool CRUD"
```

---

### Task 3: 修改 GET /api/models 合并 DB + config.yaml

**Files:**
- Modify: `backend/app/gateway/routers/models.py`

- [ ] **Step 1: 修改 list_models 函数**

找到 `async def list_models` 函数，将其替换为：

```python
@router.get(
    "/models",
    response_model=ModelsListResponse,
    summary="List All Models",
    description="返回 DB 用户自定义模型 + config.yaml 静态模型的合并列表，DB 模型优先。",
)
async def list_models(config: AppConfig = Depends(get_config)) -> ModelsListResponse:
    """合并 nail_model_configs（DB）和 config.yaml 模型，DB 优先去重。"""
    from packages.harness.deerflow.tools.nail.base import get_db

    # 1. 读 DB 中活跃的用户模型
    db_models: list[ModelResponse] = []
    db_names: set[str] = set()
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT name, model_id, display_name, use_class, "
                "supports_vision, supports_thinking FROM nail_model_configs "
                "WHERE is_active = 1 ORDER BY created_at DESC"
            ).fetchall()
        for r in rows:
            db_models.append(ModelResponse(
                name=r["name"],
                model=r["model_id"],
                display_name=r["display_name"],
                description=None,
                supports_thinking=bool(r["supports_thinking"]),
                supports_reasoning_effort=False,
            ))
            db_names.add(r["name"])
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("读取 nail_model_configs 失败（可能未初始化）: %s", e)

    # 2. config.yaml 模型（跳过已在 DB 中的同名模型）
    static_models = [
        ModelResponse(
            name=model.name,
            model=model.model,
            display_name=model.display_name,
            description=model.description,
            supports_thinking=model.supports_thinking,
            supports_reasoning_effort=model.supports_reasoning_effort,
        )
        for model in config.models
        if model.name not in db_names
    ]

    all_models = db_models + static_models
    return ModelsListResponse(
        models=all_models,
        token_usage=TokenUsageResponse(enabled=config.token_usage.enabled),
    )
```

- [ ] **Step 2: 验证语法**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/backend
python3 -c "import ast; ast.parse(open('app/gateway/routers/models.py').read()); print('语法OK')"
```

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add backend/app/gateway/routers/models.py
git commit -m "feat(api): merge DB models with config.yaml in GET /api/models"
```

---

### Task 4: 注册 nail_config router 到 app.py

**Files:**
- Modify: `backend/app/gateway/app.py`

- [ ] **Step 1: 在 app.py 顶部 import 附近添加导入**

找到 `from app.gateway.routers.nail_ops import router as nail_ops_router`，在其后添加：

```python
from app.gateway.routers.nail_config import router as nail_config_router
```

- [ ] **Step 2: 在 create_app() 中注册路由**

找到 `app.include_router(nail_ops_router)`，在其后添加：

```python
    app.include_router(nail_config_router)
```

- [ ] **Step 3: 测试后端启动**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/backend
cat /tmp/nailflow-backend.log | tail -5
# 检查新路由是否注册
curl -s http://localhost:8001/docs | grep -o "nail/config" | head -3
```

期望：后端日志无错误，`/docs` 中出现 `nail/config`

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add backend/app/gateway/app.py
git commit -m "feat(app): register nail_config_router"
```

---

## Phase 2：前端基础（类型 + Hooks）

### Task 5: 创建 nail-models 核心模块

**Files:**
- Create: `frontend/src/core/nail-models/types.ts`
- Create: `frontend/src/core/nail-models/api.ts`
- Create: `frontend/src/core/nail-models/hooks.ts`
- Create: `frontend/src/core/nail-models/index.ts`

- [ ] **Step 1: 创建 types.ts**

```typescript
// frontend/src/core/nail-models/types.ts
export type ModelProvider = "qwen" | "deepseek" | "doubao" | "kimi" | "custom";

export interface NailModelConfig {
  id: string;
  name: string;
  display_name: string;
  provider: ModelProvider;
  model_id: string;
  api_base: string;
  use_class: string;
  supports_vision: boolean;
  supports_thinking: boolean;
  is_active: boolean;
  created_at: string;
  source: "db" | "config";
}

export interface NailModelCreate {
  name: string;
  display_name: string;
  provider: ModelProvider;
  model_id: string;
  api_key?: string;
  api_base: string;
  use_class: string;
  supports_vision: boolean;
  supports_thinking: boolean;
}

export interface AgentConfigs {
  main_agent: string | null;
  tool_default: string | null;
}

export interface ToolInfo {
  name: string;
  display_name: string;
  emoji: string;
  description: string;
  group: string;
  requires_llm: boolean;
  requires_vision: boolean;
  is_enabled: boolean;
  model_override: string | null;
}

export interface ToolsResponse {
  nail_tools: ToolInfo[];
  builtin_tools: ToolInfo[];
}

/** 四大提供商预设配置 */
export const PROVIDER_PRESETS: Record<
  Exclude<ModelProvider, "custom">,
  { api_base: string; use_class: string; models: Array<{ id: string; label: string; vision?: boolean; thinking?: boolean }> }
> = {
  qwen: {
    api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    use_class: "langchain_openai:ChatOpenAI",
    models: [
      { id: "qwen-max", label: "Qwen-Max" },
      { id: "qwen-plus", label: "Qwen-Plus" },
      { id: "qwen-turbo", label: "Qwen-Turbo" },
      { id: "qwen-vl-max", label: "Qwen-VL-Max", vision: true },
    ],
  },
  deepseek: {
    api_base: "https://api.deepseek.com/v1",
    use_class: "langchain_openai:ChatOpenAI",
    models: [
      { id: "deepseek-chat", label: "DeepSeek-Chat" },
      { id: "deepseek-reasoner", label: "DeepSeek-Reasoner", thinking: true },
    ],
  },
  doubao: {
    api_base: "https://ark.cn-beijing.volces.com/api/v3",
    use_class: "deerflow.models.patched_deepseek:PatchedChatDeepSeek",
    models: [
      { id: "doubao-seed-1-8-251228", label: "Doubao-Seed-1.8", vision: true, thinking: true },
      { id: "doubao-pro-32k", label: "Doubao-Pro-32k" },
    ],
  },
  kimi: {
    api_base: "https://api.moonshot.cn/v1",
    use_class: "langchain_openai:ChatOpenAI",
    models: [
      { id: "moonshot-v1-8k", label: "Kimi-8k" },
      { id: "moonshot-v1-32k", label: "Kimi-32k" },
      { id: "moonshot-v1-128k", label: "Kimi-128k" },
    ],
  },
};
```

- [ ] **Step 2: 创建 api.ts**

```typescript
// frontend/src/core/nail-models/api.ts
import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";
import type { NailModelConfig, NailModelCreate, AgentConfigs, ToolsResponse } from "./types";

const BASE = () => `${getBackendBaseURL()}/api/nail/config`;

export async function listNailModels(): Promise<NailModelConfig[]> {
  const res = await fetch(`${BASE()}/models`);
  if (!res.ok) throw new Error(`列出模型失败: ${res.statusText}`);
  const data = await res.json();
  return data.models ?? [];
}

export async function createNailModel(body: NailModelCreate): Promise<void> {
  const res = await fetch(`${BASE()}/models`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "创建失败");
  }
}

export async function updateNailModel(name: string, body: Partial<NailModelCreate> & { is_active?: boolean }): Promise<void> {
  const res = await fetch(`${BASE()}/models/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "更新失败");
  }
}

export async function deleteNailModel(name: string): Promise<void> {
  const res = await fetch(`${BASE()}/models/${encodeURIComponent(name)}`, { method: "DELETE" });
  if (!res.ok) throw new Error("删除失败");
}

export async function getAgentConfigs(): Promise<AgentConfigs> {
  const res = await fetch(`${BASE()}/agents`);
  if (!res.ok) throw new Error("读取 Agent 配置失败");
  return res.json();
}

export async function updateAgentConfigs(configs: Partial<AgentConfigs>): Promise<void> {
  const res = await fetch(`${BASE()}/agents`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(configs),
  });
  if (!res.ok) throw new Error("更新 Agent 配置失败");
}

export async function listTools(): Promise<ToolsResponse> {
  const res = await fetch(`${BASE()}/tools`);
  if (!res.ok) throw new Error("读取工具列表失败");
  return res.json();
}

export async function updateTool(
  toolName: string,
  body: { model_name?: string | null; is_enabled?: boolean }
): Promise<void> {
  const res = await fetch(`${BASE()}/tools/${encodeURIComponent(toolName)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("更新工具配置失败");
}
```

- [ ] **Step 3: 创建 hooks.ts**

```typescript
// frontend/src/core/nail-models/hooks.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "./api";
import type { NailModelCreate, AgentConfigs } from "./types";

export const NAIL_MODELS_KEY = ["nail-models"];
export const AGENT_CONFIGS_KEY = ["nail-agent-configs"];
export const TOOLS_KEY = ["nail-tools"];
export const ALL_MODELS_KEY = ["models"];  // 与 DeerFlow 的 useModels() 共用 key

export function useNailModels() {
  return useQuery({ queryKey: NAIL_MODELS_KEY, queryFn: api.listNailModels });
}

export function useAgentConfigs() {
  return useQuery({ queryKey: AGENT_CONFIGS_KEY, queryFn: api.getAgentConfigs });
}

export function useTools() {
  return useQuery({ queryKey: TOOLS_KEY, queryFn: api.listTools });
}

export function useCreateNailModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NailModelCreate) => api.createNailModel(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: NAIL_MODELS_KEY });
      qc.invalidateQueries({ queryKey: ALL_MODELS_KEY });
    },
  });
}

export function useDeleteNailModel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.deleteNailModel(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: NAIL_MODELS_KEY });
      qc.invalidateQueries({ queryKey: ALL_MODELS_KEY });
    },
  });
}

export function useUpdateAgentConfigs() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (configs: Partial<AgentConfigs>) => api.updateAgentConfigs(configs),
    onSuccess: () => qc.invalidateQueries({ queryKey: AGENT_CONFIGS_KEY }),
  });
}

export function useUpdateTool() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { name: string; model_name?: string | null; is_enabled?: boolean }) =>
      api.updateTool(args.name, { model_name: args.model_name, is_enabled: args.is_enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: TOOLS_KEY }),
  });
}
```

- [ ] **Step 4: 创建 index.ts**

```typescript
// frontend/src/core/nail-models/index.ts
export * from "./types";
export * from "./api";
export * from "./hooks";
```

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/core/nail-models/
git commit -m "feat(frontend): add nail-models core module (types/api/hooks)"
```

---

## Phase 3：Settings「模型配置」Tab

### Task 6: 创建 model-form-dialog.tsx（添加/编辑模型表单）

**Files:**
- Create: `frontend/src/components/workspace/settings/model-form-dialog.tsx`

- [ ] **Step 1: 创建文件**

```tsx
// frontend/src/components/workspace/settings/model-form-dialog.tsx
"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  type NailModelCreate, type ModelProvider, PROVIDER_PRESETS,
} from "@/core/nail-models";
import { cn } from "@/lib/utils";

interface ModelFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (model: NailModelCreate) => Promise<void>;
  initialValues?: Partial<NailModelCreate>;
  title?: string;
}

const PROVIDERS: Array<{ id: ModelProvider; label: string; emoji: string }> = [
  { id: "qwen",     label: "千问 (Qwen)",    emoji: "🟣" },
  { id: "deepseek", label: "DeepSeek",       emoji: "🔵" },
  { id: "doubao",   label: "豆包 (Doubao)",  emoji: "🟡" },
  { id: "kimi",     label: "Kimi",           emoji: "🌙" },
  { id: "custom",   label: "自定义",          emoji: "⚙️" },
];

export function ModelFormDialog({
  open, onOpenChange, onSave, initialValues, title = "添加模型",
}: ModelFormDialogProps) {
  const [provider, setProvider] = useState<ModelProvider>(initialValues?.provider ?? "qwen");
  const [form, setForm] = useState<NailModelCreate>({
    name: "",
    display_name: "",
    provider: "qwen",
    model_id: "",
    api_key: "",
    api_base: PROVIDER_PRESETS.qwen.api_base,
    use_class: PROVIDER_PRESETS.qwen.use_class,
    supports_vision: false,
    supports_thinking: false,
    ...initialValues,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // 切换提供商时自动填充
  useEffect(() => {
    if (provider !== "custom") {
      const preset = PROVIDER_PRESETS[provider];
      setForm(f => ({
        ...f,
        provider,
        api_base: preset.api_base,
        use_class: preset.use_class,
      }));
    } else {
      setForm(f => ({ ...f, provider: "custom" }));
    }
  }, [provider]);

  const preset = provider !== "custom" ? PROVIDER_PRESETS[provider] : null;
  const presetModels = preset?.models ?? [];

  const handleSave = async () => {
    if (!form.name.trim()) { setError("名称不能为空"); return; }
    if (!form.model_id.trim()) { setError("模型 ID 不能为空"); return; }
    if (!form.api_base.trim()) { setError("API Base URL 不能为空"); return; }
    setSaving(true);
    setError("");
    try {
      await onSave(form);
      onOpenChange(false);
    } catch (e: any) {
      setError(e.message ?? "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* 提供商选择 */}
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-2">选择提供商</p>
            <div className="flex flex-wrap gap-2">
              {PROVIDERS.map(p => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setProvider(p.id)}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors",
                    provider === p.id
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground hover:border-primary/50",
                  )}
                >
                  <span>{p.emoji}</span>{p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* 名称 */}
            <div className="space-y-1">
              <label className="text-xs font-medium">名称（唯一 ID）</label>
              <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="如 qwen-max" />
            </div>
            {/* 显示名称 */}
            <div className="space-y-1">
              <label className="text-xs font-medium">显示名称</label>
              <Input value={form.display_name} onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))} placeholder="如 通义千问 Max" />
            </div>
            {/* 模型 ID */}
            <div className="col-span-2 space-y-1">
              <label className="text-xs font-medium">模型 ID</label>
              {presetModels.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {presetModels.map(m => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setForm(f => ({
                        ...f,
                        model_id: m.id,
                        display_name: f.display_name || m.label,
                        name: f.name || m.id,
                        supports_vision: m.vision ?? false,
                        supports_thinking: m.thinking ?? false,
                      }))}
                      className={cn(
                        "rounded border px-2 py-0.5 text-xs transition-colors",
                        form.model_id === m.id
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border text-muted-foreground hover:border-primary/50",
                      )}
                    >
                      {m.label}
                      {m.vision && <span className="ml-1 text-[10px] text-emerald-500">视觉</span>}
                      {m.thinking && <span className="ml-1 text-[10px] text-violet-500">思考</span>}
                    </button>
                  ))}
                </div>
              ) : null}
              <Input
                value={form.model_id}
                onChange={e => setForm(f => ({ ...f, model_id: e.target.value }))}
                placeholder="如 qwen-max"
                className="mt-1"
              />
            </div>
            {/* API Base URL */}
            <div className="col-span-2 space-y-1">
              <label className="text-xs font-medium">API Base URL</label>
              <Input value={form.api_base} onChange={e => setForm(f => ({ ...f, api_base: e.target.value }))} />
            </div>
            {/* API Key */}
            <div className="col-span-2 space-y-1">
              <label className="text-xs font-medium">API Key</label>
              <Input
                type="password"
                value={form.api_key ?? ""}
                onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
                placeholder="sk-..."
              />
            </div>
            {/* 能力开关 */}
            <div className="flex items-center gap-2">
              <Switch
                checked={form.supports_vision}
                onCheckedChange={v => setForm(f => ({ ...f, supports_vision: v }))}
              />
              <label className="text-xs">支持视觉</label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={form.supports_thinking}
                onCheckedChange={v => setForm(f => ({ ...f, supports_thinking: v }))}
              />
              <label className="text-xs">支持思考</label>
            </div>
          </div>

          {error && (
            <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/components/workspace/settings/model-form-dialog.tsx
git commit -m "feat(settings): add ModelFormDialog for adding/editing models"
```

---

### Task 7: 创建 model-settings-page.tsx（模型列表 + Agent 绑定）

**Files:**
- Create: `frontend/src/components/workspace/settings/model-settings-page.tsx`

- [ ] **Step 1: 创建文件**

```tsx
// frontend/src/components/workspace/settings/model-settings-page.tsx
"use client";

import { useState } from "react";
import { PlusIcon, Trash2Icon, PencilIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useNailModels, useAgentConfigs, useCreateNailModel,
  useDeleteNailModel, useUpdateAgentConfigs,
} from "@/core/nail-models";
import { useModels } from "@/core/models";
import { ModelFormDialog } from "./model-form-dialog";
import type { NailModelCreate } from "@/core/nail-models";

export function ModelSettingsPage() {
  const { data: nailModels = [], isLoading } = useNailModels();
  const { data: agentConfigs } = useAgentConfigs();
  const { data: allModels } = useModels();
  const createModel = useCreateNailModel();
  const deleteModel = useDeleteNailModel();
  const updateAgents = useUpdateAgentConfigs();

  const [addOpen, setAddOpen] = useState(false);
  const [deletingName, setDeletingName] = useState<string | null>(null);

  const handleCreate = async (body: NailModelCreate) => {
    await createModel.mutateAsync(body);
  };

  const handleDelete = async (name: string) => {
    setDeletingName(name);
    try { await deleteModel.mutateAsync(name); }
    finally { setDeletingName(null); }
  };

  const allModelNames = allModels?.models.map(m => ({ name: m.name, display: m.display_name ?? m.name })) ?? [];

  return (
    <div className="space-y-6">
      {/* ── 已配置模型 ── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">已配置模型</h3>
          <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
            <PlusIcon className="size-3.5 mr-1" /> 添加模型
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-2">{Array.from({length:3}).map((_,i)=><Skeleton key={i} className="h-12 rounded-lg"/>)}</div>
        ) : nailModels.length === 0 ? (
          <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            暂无自定义模型，点击「添加模型」配置千问/DeepSeek/豆包/Kimi
          </div>
        ) : (
          <div className="space-y-2">
            {nailModels.map(m => (
              <div key={m.name} className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2.5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{m.display_name}</span>
                    <Badge variant="outline" className="text-[10px] px-1.5 py-0">{m.provider}</Badge>
                    {m.supports_vision && <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-emerald-500 border-emerald-500/30">视觉</Badge>}
                    {m.supports_thinking && <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-violet-500 border-violet-500/30">思考</Badge>}
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{m.model_id}</p>
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  className="size-7 text-destructive/70 hover:text-destructive hover:bg-destructive/10 shrink-0"
                  disabled={deletingName === m.name}
                  onClick={() => handleDelete(m.name)}
                >
                  <Trash2Icon className="size-3.5" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Agent 默认模型绑定 ── */}
      <div>
        <h3 className="text-sm font-semibold mb-3">Agent 默认模型绑定</h3>
        <div className="space-y-3 rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium">主 Agent（NailPlannerAgent）</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">处理用户意图和工具调度</p>
            </div>
            <Select
              value={agentConfigs?.main_agent ?? ""}
              onValueChange={v => updateAgents.mutate({ main_agent: v })}
            >
              <SelectTrigger className="w-44 text-xs h-8">
                <SelectValue placeholder="选择模型..." />
              </SelectTrigger>
              <SelectContent>
                {allModelNames.map(m => (
                  <SelectItem key={m.name} value={m.name} className="text-xs">{m.display}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="h-px bg-border/40" />

          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium">工具默认模型</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">所有 LLM 工具的兜底模型（可在工具页单独覆盖）</p>
            </div>
            <Select
              value={agentConfigs?.tool_default ?? ""}
              onValueChange={v => updateAgents.mutate({ tool_default: v })}
            >
              <SelectTrigger className="w-44 text-xs h-8">
                <SelectValue placeholder="选择模型..." />
              </SelectTrigger>
              <SelectContent>
                {allModelNames.map(m => (
                  <SelectItem key={m.name} value={m.name} className="text-xs">{m.display}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <ModelFormDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onSave={handleCreate}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/components/workspace/settings/model-settings-page.tsx
git commit -m "feat(settings): add ModelSettingsPage with model list + agent bindings"
```

---

### Task 8: 修改 settings-dialog.tsx 插入「模型配置」Tab

**Files:**
- Modify: `frontend/src/components/workspace/settings/settings-dialog.tsx`
- Modify: `frontend/src/components/workspace/settings/index.ts`

- [ ] **Step 1: 读取 settings-dialog.tsx 确认当前 section 类型和 sections 数组**

```bash
head -100 /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/frontend/src/components/workspace/settings/settings-dialog.tsx
```

- [ ] **Step 2: 在 section 类型中插入 "models"**

找到：
```typescript
  | "account"
  | "appearance"
  | "memory"
  | "tools"
  | "skills"
  | "notification"
  | "about";
```

改为：
```typescript
  | "account"
  | "models"
  | "appearance"
  | "memory"
  | "tools"
  | "skills"
  | "notification"
  | "about";
```

- [ ] **Step 3: 在 sections 数组中插入 models 项（account 之后）**

找到 `id: "account"` 那段，在其后插入：

```typescript
      {
        id: "models",
        label: "模型配置",
        icon: CpuIcon,  // 从 lucide-react 导入
      },
```

同时在文件顶部 import 中添加 `CpuIcon`：
```typescript
import { CpuIcon } from "lucide-react";
```

- [ ] **Step 4: 在渲染 section 内容的 switch/条件 中添加 models 分支**

找到渲染各页面的地方（通常是 `activeSection === "account"` 这样的条件），添加：

```typescript
{activeSection === "models" && <ModelSettingsPage />}
```

同时在文件顶部导入：
```typescript
import { ModelSettingsPage } from "./model-settings-page";
```

- [ ] **Step 5: 更新 settings/index.ts 导出新组件**

在 `frontend/src/components/workspace/settings/index.ts` 中添加：

```typescript
export { ModelSettingsPage } from "./model-settings-page";
export { ModelFormDialog } from "./model-form-dialog";
```

- [ ] **Step 6: 在浏览器验证**

打开 `http://localhost:3001`，登录后点击左下角「设置和更多」→「设置」，确认出现「模型配置」tab，点击后页面正常显示（可能为空列表）。

- [ ] **Step 7: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/components/workspace/settings/
git commit -m "feat(settings): insert 模型配置 tab into settings dialog"
```

---

## Phase 4：工具管理页

### Task 9: 创建 model-selector-inline.tsx

**Files:**
- Create: `frontend/src/components/nail/model-selector-inline.tsx`

- [ ] **Step 1: 创建文件**

```tsx
// frontend/src/components/nail/model-selector-inline.tsx
"use client";

import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { useModels } from "@/core/models";
import { useAgentConfigs } from "@/core/nail-models";
import { cn } from "@/lib/utils";

interface ModelSelectorInlineProps {
  /** 当前选中的模型名，null 表示跟随全局 tool_default */
  value: string | null;
  onChange: (model: string | null) => void;
  /** 是否需要视觉能力（为 true 时对不支持视觉的模型显示警告） */
  requiresVision?: boolean;
  className?: string;
}

export function ModelSelectorInline({
  value, onChange, requiresVision, className,
}: ModelSelectorInlineProps) {
  const { data: allModels } = useModels();
  const { data: agentConfigs } = useAgentConfigs();

  const toolDefaultName = agentConfigs?.tool_default;
  const toolDefaultDisplay = allModels?.models.find(m => m.name === toolDefaultName)?.display_name ?? toolDefaultName ?? "未配置";

  const models = allModels?.models ?? [];

  // 注意：DeerFlow 的 ModelResponse 不含 supports_vision 字段
  // 视觉能力警告通过检查模型名称约定（含 "vl" 或 "vision" 关键词）来近似判断
  const isVisionModel = (name: string) =>
    name.toLowerCase().includes("vl") || name.toLowerCase().includes("vision");

  return (
    <div className={cn("space-y-1", className)}>
      <p className="text-[11px] font-medium text-muted-foreground">模型绑定</p>
      <Select
        value={value ?? "__default__"}
        onValueChange={v => onChange(v === "__default__" ? null : v)}
      >
        <SelectTrigger className="h-7 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__default__" className="text-xs">
            <span className="text-muted-foreground">工具默认（{toolDefaultDisplay}）</span>
          </SelectItem>
          {models.map(m => (
            <SelectItem key={m.name} value={m.name} className="text-xs">
              <span>{m.display_name ?? m.name}</span>
              {m.supports_thinking && <span className="ml-1 text-[10px] text-violet-400">思考</span>}
              {isVisionModel(m.name) && <span className="ml-1 text-[10px] text-emerald-400">视觉</span>}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {requiresVision && value && !isVisionModel(value) && (
        <p className="text-[10px] text-amber-500">⚠️ 此工具需要视觉能力，建议选择名称含 vl/vision 的模型</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/components/nail/model-selector-inline.tsx
git commit -m "feat(nail): add ModelSelectorInline for tool cards"
```

---

### Task 10: 创建 tool-card.tsx

**Files:**
- Create: `frontend/src/components/nail/tool-card.tsx`

- [ ] **Step 1: 创建文件**

```tsx
// frontend/src/components/nail/tool-card.tsx
"use client";

import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { useUpdateTool } from "@/core/nail-models";
import { ModelSelectorInline } from "./model-selector-inline";
import type { ToolInfo } from "@/core/nail-models";
import { cn } from "@/lib/utils";

const GROUP_COLORS: Record<string, string> = {
  nail:     "bg-rose-500/10 text-rose-400 border-rose-400/20",
  nail_ops: "bg-emerald-500/10 text-emerald-400 border-emerald-400/20",
  nail_dev: "bg-blue-500/10 text-blue-400 border-blue-400/20",
  web:      "bg-sky-500/10 text-sky-400 border-sky-400/20",
  file:     "bg-amber-500/10 text-amber-400 border-amber-400/20",
  bash:     "bg-violet-500/10 text-violet-400 border-violet-400/20",
};

interface ToolCardProps {
  tool: ToolInfo;
}

export function ToolCard({ tool }: ToolCardProps) {
  const updateTool = useUpdateTool();

  const handleToggle = (enabled: boolean) => {
    updateTool.mutate({ name: tool.name, is_enabled: enabled });
  };

  const handleModelChange = (model: string | null) => {
    updateTool.mutate({ name: tool.name, model_name: model });
  };

  return (
    <div
      className={cn(
        "rounded-xl border bg-card px-4 py-3 transition-opacity",
        !tool.is_enabled && "opacity-50",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold">
              {tool.emoji} {tool.display_name}
            </span>
            <Badge
              variant="outline"
              className={cn("text-[10px] px-1.5 py-0", GROUP_COLORS[tool.group])}
            >
              {tool.group}
            </Badge>
            {tool.requires_llm && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-muted-foreground border-border/50">
                LLM
              </Badge>
            )}
            {tool.requires_vision && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-emerald-400 border-emerald-400/20">
                视觉
              </Badge>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
            {tool.description}
          </p>
        </div>
        <Switch
          checked={tool.is_enabled}
          onCheckedChange={handleToggle}
          disabled={updateTool.isPending}
          className="shrink-0 mt-0.5"
        />
      </div>

      {/* 仅需要 LLM 的工具显示模型选择器 */}
      {tool.requires_llm && tool.is_enabled && (
        <div className="mt-3 pt-3 border-t border-border/40">
          <ModelSelectorInline
            value={tool.model_override}
            onChange={handleModelChange}
            requiresVision={tool.requires_vision}
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/components/nail/tool-card.tsx
git commit -m "feat(nail): add ToolCard with toggle and model selector"
```

---

### Task 11: 创建工具管理页 + 更新 NailNav

**Files:**
- Create: `frontend/src/app/workspace/nail/tools/page.tsx`
- Modify: `frontend/src/components/workspace/nail-nav.tsx`

- [ ] **Step 1: 创建工具管理页**

```tsx
// frontend/src/app/workspace/nail/tools/page.tsx
"use client";

import { useState } from "react";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useTools } from "@/core/nail-models";
import { ToolCard } from "@/components/nail/tool-card";

export default function ToolsPage() {
  const { data: toolsData, isLoading } = useTools();
  const [search, setSearch] = useState("");

  const filter = (name: string, desc: string) =>
    !search || name.toLowerCase().includes(search.toLowerCase()) || desc.toLowerCase().includes(search.toLowerCase());

  const nailTools = (toolsData?.nail_tools ?? []).filter(t => filter(t.display_name, t.description));
  const builtinTools = (toolsData?.builtin_tools ?? []).filter(t => filter(t.display_name, t.description));

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="mr-2 h-4" />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden sm:block text-muted-foreground">NailFlow</BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>工具管理</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto w-48">
          <Input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索工具..."
            className="h-7 text-xs"
          />
        </div>
      </header>

      <ScrollArea className="flex-1">
        <div className="mx-auto max-w-2xl px-4 py-6 space-y-8">

          {/* NailFlow 工具 */}
          <section>
            <div className="mb-3">
              <h2 className="text-sm font-semibold">NailFlow 工具</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                美甲试戴专属工具链，支持按角色权限（nail / nail_ops / nail_dev）过滤
              </p>
            </div>
            {isLoading ? (
              <div className="space-y-2">{Array.from({length:5}).map((_,i)=><Skeleton key={i} className="h-20 rounded-xl"/>)}</div>
            ) : nailTools.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">没有匹配的工具</p>
            ) : (
              <div className="space-y-2">
                {nailTools.map(t => <ToolCard key={t.name} tool={t} />)}
              </div>
            )}
          </section>

          {/* DeerFlow 内置工具 */}
          <section>
            <div className="mb-3">
              <h2 className="text-sm font-semibold">DeerFlow 内置工具</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                网页搜索、文件操作、命令执行等通用工具
              </p>
            </div>
            {isLoading ? (
              <div className="space-y-2">{Array.from({length:3}).map((_,i)=><Skeleton key={i} className="h-16 rounded-xl"/>)}</div>
            ) : builtinTools.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">没有匹配的工具</p>
            ) : (
              <div className="space-y-2">
                {builtinTools.map(t => <ToolCard key={t.name} tool={t} />)}
              </div>
            )}
          </section>

          <div className="h-4" />
        </div>
      </ScrollArea>
    </div>
  );
}
```

- [ ] **Step 2: 在 nail-nav.tsx 添加 🔧 工具 导航项**

找到 `NAV_ITEMS` 数组，在 "评分面板" 之前插入：

```typescript
  { href: "/workspace/nail/tools", label: "工具管理", emoji: "🔧", requiredRole: "user" },
```

完整更新后的 `NAV_ITEMS`：
```typescript
const NAV_ITEMS: NailNavItem[] = [
  { href: "/workspace/chats/new?mode=nail", label: "AI 试戴",  emoji: "💅", requiredRole: "user" },
  { href: "/workspace/nail/tools",          label: "工具管理", emoji: "🔧", requiredRole: "user" },
  { href: "/workspace/nail/dashboard",      label: "运营看板", emoji: "📊", requiredRole: "ops" },
  { href: "/workspace/nail/evaluation",     label: "评分面板", emoji: "⚡", requiredRole: "dev" },
];
```

- [ ] **Step 3: 验证工具页正常显示**

浏览器访问 `http://localhost:3001/workspace/nail/tools`，确认：
- 左侧 NailFlow 导航出现 "🔧 工具管理"
- 页面展示 NailFlow 工具（13 个）和 DeerFlow 内置工具（5 个）
- 每张卡片有开关，LLM 工具有模型下拉

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/app/workspace/nail/tools/ \
        frontend/src/components/workspace/nail-nav.tsx
git commit -m "feat(tools): add tools management page and nail-nav entry"
```

---

## Phase 5：对话页模型快速选择器

### Task 12: 创建 NailModelPicker 组件

**Files:**
- Create: `frontend/src/components/nail/nail-model-picker.tsx`

- [ ] **Step 1: 创建文件**

```tsx
// frontend/src/components/nail/nail-model-picker.tsx
"use client";

import { BotIcon, Settings2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useModels } from "@/core/models";
import { useAgentConfigs } from "@/core/nail-models";
import { cn } from "@/lib/utils";

interface NailModelPickerProps {
  /** 当前会话选中的模型名（来自 localStorage） */
  value?: string;
  onChange: (model: string) => void;
  className?: string;
}

export function NailModelPicker({ value, onChange, className }: NailModelPickerProps) {
  const { data: modelsData } = useModels();
  const { data: agentConfigs } = useAgentConfigs();

  const models = modelsData?.models ?? [];
  const defaultModelName = agentConfigs?.main_agent;
  const currentModel = models.find(m => m.name === value)
    ?? models.find(m => m.name === defaultModelName)
    ?? models[0];

  if (models.length === 0) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn("h-7 gap-1.5 text-xs font-medium", className)}
        >
          <BotIcon className="size-3.5 text-muted-foreground" />
          {currentModel?.display_name ?? currentModel?.name ?? "选择模型"}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        <p className="px-2 py-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
          当前会话主 Agent 模型
        </p>
        {models.map(m => (
          <DropdownMenuItem
            key={m.name}
            onClick={() => onChange(m.name)}
            className="text-xs flex items-center justify-between"
          >
            <span className={cn(value === m.name || (!value && m.name === defaultModelName) ? "font-semibold" : "")}>
              {m.display_name ?? m.name}
            </span>
            <div className="flex gap-1">
              {m.supports_thinking && (
                <span className="text-[10px] text-violet-400">思考</span>
              )}
            </div>
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="text-xs text-muted-foreground"
          onClick={() => {
            // 打开 Settings 模型配置 tab
            document.dispatchEvent(new CustomEvent("open-settings", { detail: { section: "models" } }));
          }}
        >
          <Settings2Icon className="size-3 mr-1.5" />
          配置更多模型…
        </DropdownMenuTrigger>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

**注意**：上面代码有 `</DropdownMenuTrigger>` 误用，实际最后一个 DropdownMenuItem 应用 `</DropdownMenuItem>` 结尾。正确代码如下修正最后 DropdownMenuItem：

```tsx
        <DropdownMenuItem
          className="text-xs text-muted-foreground"
          onClick={() => {
            document.dispatchEvent(new CustomEvent("open-settings", { detail: { section: "models" } }));
          }}
        >
          <Settings2Icon className="size-3 mr-1.5" />
          配置更多模型…
        </DropdownMenuItem>
```

- [ ] **Step 2: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/components/nail/nail-model-picker.tsx
git commit -m "feat(nail): add NailModelPicker for per-session model selection"
```

---

### Task 13: 修改对话页插入 NailModelPicker

**Files:**
- Modify: `frontend/src/app/workspace/chats/[thread_id]/page.tsx`

- [ ] **Step 1: 读取对话页头部 header 区域**

```bash
sed -n '120,175p' '/Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/frontend/src/app/workspace/chats/[thread_id]/page.tsx'
```

- [ ] **Step 2: 在 header 的 Tokens 按钮左侧插入 NailModelPicker**

在文件顶部添加导入：
```typescript
import { NailModelPicker } from "@/components/nail/nail-model-picker";
import { useSearchParams } from "next/navigation";
```

在对话页顶部 header 的 Tokens 按钮之前，插入：
```tsx
{/* Nail 模式显示模型选择器 */}
<div className="ml-auto flex items-center gap-2">
  <NailModelPicker
    value={settings.context.model_name}
    onChange={(model) => setSettings("context", { ...settings.context, model_name: model })}
  />
  <TokenUsageIndicator ... />
</div>
```

**注意**：对话页的 header 区域结构需要先读取确认，再做精确修改。实际插入时不要破坏现有 layout，只在 Tokens 左侧加一个按钮。

- [ ] **Step 3: 验证**

访问 `http://localhost:3001/workspace/chats/new?mode=nail`，确认顶部出现模型选择按钮。

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add frontend/src/app/workspace/chats/[thread_id]/page.tsx
git commit -m "feat(chat): insert NailModelPicker in chat page header"
```

---

## Phase 6：后端 Agent 读取配置

### Task 14: 修改 lead_agent 读取 nail_agent_configs

**Files:**
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/agent.py`

- [ ] **Step 1: 在 _get_runtime_config 之后、get_available_tools 之前读取 nail_agent_configs**

找到 `nail_role = cfg.get("nail_role", "user")` 这行（Task 9 中添加的），在其后追加：

```python
# 读取 nail_agent_configs 的主 Agent 模型绑定（覆盖 model_name）
_requested_model = cfg.get("model_name")
if not _requested_model:
    try:
        from packages.harness.deerflow.tools.nail.base import get_db
        with get_db() as _db:
            _row = _db.execute(
                "SELECT model_name FROM nail_agent_configs WHERE config_key='main_agent'"
            ).fetchone()
            if _row and _row["model_name"]:
                cfg["model_name"] = _row["model_name"]
    except Exception as _e:
        pass  # DB 未初始化时静默忽略
```

- [ ] **Step 2: 验证**

在设置页配置一个模型，绑定到主 Agent，然后发一条消息，检查 backend 日志中使用的模型名。

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add backend/packages/harness/deerflow/agents/lead_agent/agent.py
git commit -m "feat(agent): read nail_agent_configs main_agent model binding"
```

---

### Task 15: 修改 LLM 工具读取 nail_tool_overrides

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/style_understanding.py`
- Modify: `backend/packages/harness/deerflow/tools/nail/quality_check.py`
- Modify: `backend/packages/harness/deerflow/tools/nail/ops_analysis.py`
- Modify: `backend/packages/harness/deerflow/tools/nail/customer_service.py`
- Modify: `backend/packages/harness/deerflow/tools/nail/trend_discovery.py`
- Modify: `backend/packages/harness/deerflow/tools/nail/evaluation.py`

- [ ] **Step 1: 在 base.py 添加工具模型查询帮助函数**

在 `backend/packages/harness/deerflow/tools/nail/base.py` 末尾追加：

```python
def get_tool_model(tool_name: str) -> str | None:
    """读取工具的模型覆盖配置，返回 model_name 或 None（表示用全局默认）。"""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT model_name FROM nail_tool_overrides WHERE tool_name = ? AND is_enabled = 1",
                (tool_name,)
            ).fetchone()
            if row:
                return row["model_name"]
            # 无工具覆盖时，读全局 tool_default
            default = conn.execute(
                "SELECT model_name FROM nail_agent_configs WHERE config_key = 'tool_default'"
            ).fetchone()
            return default["model_name"] if default else None
    except Exception:
        return None
```

- [ ] **Step 2: 修改每个 LLM 工具的 create_chat_model() 调用**

以 `style_understanding.py` 为例，找到：
```python
model = create_chat_model(thinking_enabled=False, attach_tracing=False)
```

改为：
```python
from .base import get_tool_model
_model_name = get_tool_model("style_understanding_tool")
model = create_chat_model(
    name=_model_name,
    thinking_enabled=False,
    attach_tracing=False,
)
```

对以下工具逐一做同样修改（tool_name 对应各自的工具函数名）：
- `quality_check.py` → `"quality_check_tool"`
- `ops_analysis.py` → `"ops_analysis_tool"`
- `customer_service.py` → `"customer_service_tool"`
- `trend_discovery.py` → `"trend_discovery_tool"`
- `evaluation.py` → `"evaluation_tool"`

- [ ] **Step 3: Commit**

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai
git add backend/packages/harness/deerflow/tools/nail/
git commit -m "feat(tools): read nail_tool_overrides for per-tool model selection"
```

---

## 验收检查

- [ ] `GET /api/nail/config/models` 返回 200（空数组）
- [ ] `POST /api/nail/config/models` 创建模型 → `GET /api/models` 返回合并结果
- [ ] Settings → 模型配置 tab 可见，可添加一个千问模型
- [ ] 工具管理页 `/workspace/nail/tools` 显示 13 + 5 个工具
- [ ] 工具页 LLM 工具有模型下拉，切换后刷新页面仍保持
- [ ] 对话页顶部出现模型选择按钮
- [ ] 侧边栏 NailFlow 区块出现 🔧 工具管理

---

## 快速参考：后端启动

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/backend
export PATH="$HOME/.local/bin:$PATH"
PYTHONPATH=. uv run uvicorn app.gateway.app:app --port 8001 --reload
```

## 快速参考：前端启动

```bash
cd /Users/zhangkai169/Desktop/美团黑客松-ai美甲试戴和运营/hackathon-meituan-ai/frontend
export PATH="$HOME/.nvm/versions/node/v24.14.0/bin:$PATH"
PORT=3001 pnpm dev
```
