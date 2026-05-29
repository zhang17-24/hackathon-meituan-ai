# NailFlow 三端 ReAct Agent + RAG 推荐系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让运营看板和评分面板获得 DeerFlow ReAct chat 界面（C布局），每个页面独立 Agent 配置（提示词+工具集），并重构 RAG 为图片向量偏好推荐系统。

**Architecture:** 单一 lead_agent 通过 `nail_page_mode` configurable 参数切换行为（提示词前缀+工具组）；前端 localStorage 按用户+页面隔离 thread_id；运营/评分页面采用「数据面板默认，点击 AI 分析后 chat 滑入右侧40%」布局；RAG 重构为单一 `nail_styles` ChromaDB collection + `nail_user_prefs` SQLite 表存储每用户偏好向量，用加权滑动平均更新。

**Tech Stack:** FastAPI、LangGraph(DeerFlow)、ChromaDB、SQLite、Next.js 16、React Query v5、ECharts（已有）、Tailwind CSS

**所有后端命令在 `backend/` 目录下执行，所有前端命令在 `frontend/` 目录下执行。**

---

## 文件改动清单

### 后端新建
- `backend/packages/harness/deerflow/tools/nail/nail_style_recommend.py`
- `backend/packages/harness/deerflow/tools/nail/user_pref_analytics.py`
- `backend/packages/harness/deerflow/tools/nail/nail_run_query.py`
- `backend/scripts/init_nail_styles.py`

### 后端修改
- `backend/packages/harness/deerflow/tools/nail/base.py`（新增2表+1列+update_user_pref_vector）
- `backend/packages/harness/deerflow/tools/nail/preference_rag.py`（重构）
- `backend/packages/harness/deerflow/agents/lead_agent/agent.py`（nail_page_mode注入+tool_call_log中间件）
- `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`（MODE_PROMPT_PREFIX+apply_prompt_template新参数）
- `backend/app/gateway/routers/nail_config.py`（新增page-mode端点+enabled_pages支持）
- `backend/app/gateway/routers/nail_ops.py`（新增save_style+pref_distribution+dashboard扩展）
- `backend/config.yaml`（注册3个新工具）

### 前端新建
- `frontend/src/core/nail-chat/use-nail-thread.ts`
- `frontend/src/core/nail-chat/use-nail-chat.ts`
- `frontend/src/core/nail-chat/index.ts`
- `frontend/src/components/nail/nail-page-layout.tsx`
- `frontend/src/components/nail/nail-chat-pane.tsx`
- `frontend/src/components/nail/tool-timeline.tsx`

### 前端修改
- `frontend/src/app/workspace/nail/dashboard/page.tsx`（使用NailPageLayout+ECharts）
- `frontend/src/app/workspace/nail/evaluation/page.tsx`（使用NailPageLayout+ToolTimeline）
- `frontend/src/components/nail/tool-card.tsx`（新增enabled_pages开关）

---

## Task 1: 数据库 Schema 扩展

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/base.py`

- [ ] **Step 1: 在 `init_nail_tables()` 的 `executescript` 末尾追加3个新建表/列语句**

找到 `base.py` 中 `CREATE TABLE IF NOT EXISTS nail_tool_overrides` 那段末尾的 `""")` 之前，在最后一个表之后添加：

```python
            CREATE TABLE IF NOT EXISTS tool_call_log (
                id          TEXT PRIMARY KEY,
                run_id      TEXT NOT NULL,
                tool_name   TEXT NOT NULL,
                call_index  INTEGER DEFAULT 0,
                input_json  TEXT,
                output_json TEXT,
                thinking    TEXT,
                duration_ms INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS nail_user_prefs (
                user_id     TEXT PRIMARY KEY,
                pref_vector TEXT NOT NULL,
                trial_count INTEGER DEFAULT 0,
                save_count  INTEGER DEFAULT 0,
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS nail_style_catalog (
                style_id    TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                category    TEXT,
                color_tags  TEXT,
                image_path  TEXT,
                source      TEXT DEFAULT 'static'
            );
```

同时在 `nail_tool_overrides` 表的 `updated_at` 行之前加 `enabled_pages TEXT DEFAULT '["tryon","ops","eval"]',`（注意这个新列对已存在的表需要 ALTER）。

在 `init_nail_tables()` 函数末尾 `logger.info(...)` 之前追加：

```python
    # 幂等地为 nail_tool_overrides 添加 enabled_pages 列（已有列时忽略报错）
    try:
        with get_db() as conn:
            conn.execute(
                "ALTER TABLE nail_tool_overrides ADD COLUMN enabled_pages TEXT DEFAULT '[\"tryon\",\"ops\",\"eval\"]'"
            )
    except Exception:
        pass  # 列已存在，忽略
```

- [ ] **Step 2: 在 `base.py` 末尾添加 `update_user_pref_vector` 函数**

```python
def update_user_pref_vector(user_id: str, style_id: str, signal_type: str) -> None:
    """用加权滑动平均更新用户偏好向量。

    HISTORY_DECAY=0.8, NEW_SIGNAL_RATIO=0.2
    signal_weight: tryon=1.0, save=3.0, search=2.0
    """
    import json as _json
    try:
        import numpy as np
    except ImportError:
        logger.warning("numpy not installed, skipping pref vector update")
        return

    SIGNAL_WEIGHT = {"tryon": 1.0, "save": 3.0, "search": 2.0}
    HISTORY_DECAY = 0.8
    NEW_SIGNAL_RATIO = 0.2

    try:
        # 1. 获取款式向量（从 ChromaDB）
        import chromadb
        from chromadb.utils import embedding_functions
        chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
        client = chromadb.PersistentClient(path=chroma_dir)
        ef = embedding_functions.DefaultEmbeddingFunction()
        col = client.get_or_create_collection("nail_styles", embedding_function=ef)

        result = col.get(ids=[style_id], include=["embeddings"])
        if not result["embeddings"]:
            logger.debug("update_user_pref_vector: style_id %s not in ChromaDB", style_id)
            return
        style_vec = np.array(result["embeddings"][0], dtype=float)

        # 2. 获取用户历史偏好向量
        with get_db() as conn:
            row = conn.execute(
                "SELECT pref_vector FROM nail_user_prefs WHERE user_id=?", (user_id,)
            ).fetchone()

        weight = SIGNAL_WEIGHT.get(signal_type, 1.0)

        if row is None:
            new_pref = style_vec * weight
        else:
            old_pref = np.array(_json.loads(row["pref_vector"]), dtype=float)
            new_pref = old_pref * HISTORY_DECAY + style_vec * NEW_SIGNAL_RATIO * weight

        # 归一化
        norm = float(np.linalg.norm(new_pref))
        if norm > 0:
            new_pref = new_pref / norm

        # 3. 更新 DB
        col_field = "trial_count" if signal_type == "tryon" else "save_count"
        with get_db() as conn:
            conn.execute("""
                INSERT INTO nail_user_prefs (user_id, pref_vector, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    pref_vector = excluded.pref_vector,
                    updated_at  = excluded.updated_at
            """, (user_id, _json.dumps(new_pref.tolist())))
            conn.execute(
                f"UPDATE nail_user_prefs SET {col_field} = {col_field} + 1 WHERE user_id = ?",
                (user_id,)
            )

    except Exception as e:
        logger.error("update_user_pref_vector failed (user=%s style=%s): %s", user_id, style_id, e)
```

- [ ] **Step 3: 验证 DB 初始化**

```bash
cd /path/to/hackathon-meituan-ai/backend
python -c "
from packages.harness.deerflow.tools.nail.base import init_nail_tables
init_nail_tables()
print('OK')
"
```

期望输出：`OK`（无报错）

- [ ] **Step 4: 验证新表存在**

```bash
sqlite3 data/nailflow.db ".tables"
```

期望输出包含：`tool_call_log  nail_user_prefs  nail_style_catalog`

---

## Task 2: nail_page_mode 后端注入（Agent + Prompt）

**Files:**
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/agent.py`

- [ ] **Step 1: 在 `prompt.py` 中扩展 `_NAIL_ROLE_PREFIX` 为按 mode 的提示词**

在 `_NAIL_ROLE_PREFIX` 字典（约第768行）之后、`apply_prompt_template` 函数之前，添加：

```python
# 按页面 mode 覆盖提示词前缀（优先级高于 nail_role）
_NAIL_PAGE_MODE_PREFIX = {
    "tryon": (
        "你是 NailFlow AI 美甲试戴助手。专注于帮助用户完成 AI 试戴全流程。\n"
        "试戴工具链：hand_detect_tool → nail_mask_tool → style_understanding_tool "
        "→ prompt_builder_tool → image_generation_tool → quality_check_tool。\n"
        "试戴完成后主动调用 nail_style_recommend_tool 为用户推荐相似款式。\n"
        "用中文回复，语气亲切专业。\n\n"
    ),
    "ops": (
        "你是 NailFlow 智能运营助手。分析美甲运营数据、发现趋势、生成营销方案。\n"
        "工作流程：trend_query_tool → trend_discovery_tool → ops_analysis_tool → action_proposal_tool。\n"
        "需要了解用户偏好分布时调用 user_pref_analytics_tool。\n"
        "所有影响价格/库存/预约/退款的操作必须先生成 ActionProposal 等待人工确认。\n"
        "回复中标注数据来源，用 Markdown 表格展示数据，用清晰结构呈现方案。\n\n"
    ),
    "eval": (
        "你是 NailFlow 评分分析助手。评估 AI 试戴质量，提供改进建议。\n"
        "分析流程：nail_run_query_tool（获取最近试戴数据）→ evaluation_tool（按赛题评分）。\n"
        "评分时覆盖：完整性(30)、应用效果(25)、创新性(20)、商业价值(15)、硬约束(10)。\n"
        "给出具体扣分原因和按评分收益排序的下一步开发任务。\n"
        "详细展示工具调用过程，便于调试和答辩举证。\n\n"
    ),
}
```

- [ ] **Step 2: 修改 `apply_prompt_template` 函数签名，增加 `nail_page_mode` 参数**

找到 `def apply_prompt_template(` 函数（约第786行），将签名改为：

```python
def apply_prompt_template(
    subagent_enabled: bool = False,
    max_concurrent_subagents: int = 3,
    *,
    agent_name: str | None = None,
    available_skills: set[str] | None = None,
    app_config: AppConfig | None = None,
    nail_role: str = "user",
    nail_page_mode: str = "tryon",
) -> str:
```

并把函数内的这一行：
```python
    role_prefix = _NAIL_ROLE_PREFIX.get(nail_role, _NAIL_ROLE_PREFIX["user"])
```
改为：
```python
    # page_mode 优先，没有 page_mode 时退回到 nail_role 前缀
    role_prefix = _NAIL_PAGE_MODE_PREFIX.get(
        nail_page_mode,
        _NAIL_ROLE_PREFIX.get(nail_role, _NAIL_ROLE_PREFIX["user"])
    )
```

- [ ] **Step 3: 在 `agent.py` 中读取 nail_page_mode 并过滤工具**

在约第409行 `nail_groups = _ROLE_GROUPS.get(nail_role, ["nail"])` 之后插入：

```python
    # NailFlow: page_mode 控制工具子集（在 nail_role 权限内进一步过滤）
    nail_page_mode = cfg.get("nail_page_mode", "tryon")
    _MODE_TOOL_GROUPS = {
        "tryon": ["nail"],
        "ops":   ["nail", "nail_ops"],
        "eval":  ["nail", "nail_ops", "nail_dev"],
    }
    mode_groups = _MODE_TOOL_GROUPS.get(nail_page_mode, ["nail"])
    # 取交集：mode 要求的组 ∩ nail_role 有权访问的组
    nail_groups = [g for g in mode_groups if g in nail_groups]
    if not nail_groups:
        nail_groups = ["nail"]  # 降级到最小权限
```

- [ ] **Step 4: 在 `agent.py` 中把 `nail_page_mode` 传给 `apply_prompt_template`**

找到两处 `apply_prompt_template(` 调用（约486行和512行），在每处调用中，在 `nail_role=nail_role,` 之后追加 `nail_page_mode=nail_page_mode,`：

```python
        # bootstrap agent（约491行）
        system_prompt=apply_prompt_template(
            subagent_enabled=subagent_enabled,
            max_concurrent_subagents=max_concurrent_subagents,
            available_skills=set(["bootstrap"]),
            app_config=resolved_app_config,
            nail_role=nail_role,
            nail_page_mode=nail_page_mode,   # ← 新增
        ),

        # 正常 agent（约512行）
        system_prompt=apply_prompt_template(
            subagent_enabled=subagent_enabled,
            max_concurrent_subagents=max_concurrent_subagents,
            agent_name=agent_name,
            available_skills=set(agent_config.skills) if agent_config and agent_config.skills is not None else None,
            app_config=resolved_app_config,
            nail_role=nail_role,
            nail_page_mode=nail_page_mode,   # ← 新增
        ),
```

- [ ] **Step 5: 验证后端启动无报错**

```bash
cd /path/to/hackathon-meituan-ai/backend
uv run python -c "
from packages.harness.deerflow.agents.lead_agent.prompt import apply_prompt_template
p = apply_prompt_template(nail_role='ops', nail_page_mode='ops')
assert '运营助手' in p, 'ops prefix missing'
p2 = apply_prompt_template(nail_role='dev', nail_page_mode='eval')
assert '评分分析' in p2, 'eval prefix missing'
print('prompt OK')
"
```

期望输出：`prompt OK`

---

## Task 3: Tool page-mode 过滤（nail_config 扩展）

**Files:**
- Modify: `backend/app/gateway/routers/nail_config.py`

- [ ] **Step 1: 扩展 ToolUpdateRequest Pydantic 模型**

找到 `nail_config.py` 中处理工具更新的 Pydantic 模型（搜索 `is_enabled`），在该模型中添加 `enabled_pages` 字段：

```python
class ToolUpdateRequest(BaseModel):
    is_enabled: Optional[bool] = None
    model_name: Optional[str] = None
    enabled_pages: Optional[list[str]] = None  # 新增：["tryon","ops","eval"] 的子集
```

- [ ] **Step 2: 修改 `PUT /api/nail/config/tools/{tool_name}` 处理 enabled_pages**

找到对应的端点函数，在更新 `is_enabled` 和 `model_name` 的逻辑后追加：

```python
        if body.enabled_pages is not None:
            import json as _json
            conn.execute(
                "UPDATE nail_tool_overrides SET enabled_pages=?, updated_at=datetime('now') WHERE tool_name=?",
                (_json.dumps(body.enabled_pages), tool_name)
            )
```

- [ ] **Step 3: 在 `GET /api/nail/config/tools` 响应中包含 enabled_pages**

找到查询工具列表的 SQL，在 SELECT 字段中加 `enabled_pages`，并在返回的工具字典中加：

```python
"enabled_pages": json.loads(row["enabled_pages"]) if row.get("enabled_pages") else ["tryon","ops","eval"],
```

- [ ] **Step 4: 新增 `GET /api/nail/config/page-mode/{mode}` 端点**

在 `nail_config.py` 末尾添加：

```python
_PAGE_MODE_CONFIG = {
    "tryon": {
        "title": "AI 美甲试戴助手",
        "subtitle": "上传手图和款式图，开始 AI 试戴",
        "suggestions": [
            "帮我试戴这款法式美甲",
            "推荐适合我肤色的款式",
            "这个款式适合日常吗？",
        ],
    },
    "ops": {
        "title": "运营分析助手",
        "subtitle": "分析趋势数据，生成运营方案",
        "suggestions": [
            "分析本周热门美甲款式",
            "生成本月营销方案",
            "查看用户偏好风格分布",
        ],
    },
    "eval": {
        "title": "评分分析助手",
        "subtitle": "评估试戴质量，生成答辩证据",
        "suggestions": [
            "分析最近一次 AI 试戴质量",
            "当前系统哪里扣分最多？",
            "生成答辩证据清单",
        ],
    },
}


@router.get("/page-mode/{mode}")
async def get_page_mode_config(mode: str):
    """返回指定页面模式的欢迎语和建议问题。"""
    return _PAGE_MODE_CONFIG.get(mode, _PAGE_MODE_CONFIG["tryon"])
```

- [ ] **Step 5: 验证新端点**

```bash
curl -s http://localhost:8001/api/nail/config/page-mode/ops | python3 -m json.tool
```

期望输出包含 `"title": "运营分析助手"`

---

## Task 4: RAG 推荐系统重构

**Files:**
- Modify: `backend/packages/harness/deerflow/tools/nail/preference_rag.py`（重构）
- Create: `backend/packages/harness/deerflow/tools/nail/nail_style_recommend.py`
- Create: `backend/scripts/init_nail_styles.py`

- [ ] **Step 1: 重写 `preference_rag.py` 为偏好向量更新工具**

将 `preference_rag.py` 内容完全替换为：

```python
# backend/packages/harness/deerflow/tools/nail/preference_rag.py
"""用户偏好 RAG：保存试戴/收藏信号，更新用户偏好向量。"""
import json
import logging

from langchain.tools import tool

from .base import get_db, update_user_pref_vector

logger = logging.getLogger(__name__)


@tool
def preference_rag_tool(action: str, user_id: str, style_id: str = "", data: str = "") -> str:
    """保存用户美甲偏好信号，更新偏好向量用于个性化推荐。

    Args:
        action: "save"（保存偏好信号）或 "get_stats"（查询用户偏好统计）。
        user_id: 用户唯一标识。
        style_id: 款式 ID（action=save 时必填）。
        data: action=save 时信号类型："tryon"（试戴,弱信号）/"save"（收藏,强信号）/"search"（搜索）。

    Returns:
        action=save: {"saved": true, "signal_type": "..."}
        action=get_stats: {"trial_count": n, "save_count": n, "has_preference": bool}
        失败时: {"error": "...", "saved": false}
    """
    try:
        if action == "save":
            signal_type = data if data in ("tryon", "save", "search") else "tryon"
            update_user_pref_vector(user_id, style_id, signal_type)
            # 同步写入 ops_signals（供运营看板使用）
            if signal_type in ("save", "tryon"):
                with get_db() as conn:
                    conn.execute(
                        "INSERT INTO ops_signals (user_id, style_id, signal_type) VALUES (?,?,?)",
                        (user_id, style_id, signal_type)
                    )
            return json.dumps({"saved": True, "signal_type": signal_type}, ensure_ascii=False)

        elif action == "get_stats":
            with get_db() as conn:
                row = conn.execute(
                    "SELECT trial_count, save_count FROM nail_user_prefs WHERE user_id=?",
                    (user_id,)
                ).fetchone()
            if row is None:
                return json.dumps({"trial_count": 0, "save_count": 0, "has_preference": False})
            return json.dumps({
                "trial_count": row["trial_count"],
                "save_count": row["save_count"],
                "has_preference": True,
            }, ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知 action: {action}，请用 save 或 get_stats"})

    except Exception as e:
        logger.error("PreferenceRAG error (action=%s): %s", action, e)
        return json.dumps({"error": str(e), "saved": False})
```

- [ ] **Step 2: 创建 `nail_style_recommend.py`**

```python
# backend/packages/harness/deerflow/tools/nail/nail_style_recommend.py
"""基于用户偏好向量，在款式向量空间中查找最近邻，返回推荐款式。"""
import json
import logging
import os

from langchain.tools import tool

from .base import get_db

logger = logging.getLogger(__name__)

_CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")


def _get_nail_styles_collection():
    import chromadb
    from chromadb.utils import embedding_functions
    client = chromadb.PersistentClient(path=_CHROMA_DIR)
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection("nail_styles", embedding_function=ef)


def _cold_start_recommend(top_k: int) -> str:
    """冷启动：返回 ops_signals 中点击量最高的款式。"""
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT style_id, COUNT(*) as cnt
                FROM ops_signals
                WHERE signal_type IN ('click','save','order')
                GROUP BY style_id
                ORDER BY cnt DESC
                LIMIT ?
            """, (top_k,)).fetchall()
        recs = [{"style_id": r["style_id"], "description": "热门款式", "similarity": 0.8}
                for r in rows]
        return json.dumps({
            "recommendations": recs,
            "count": len(recs),
            "message": "暂无偏好记录，推荐热门款式",
            "is_cold_start": True,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"recommendations": [], "count": 0, "error": str(e)})


@tool
def nail_style_recommend_tool(user_id: str, top_k: int = 5) -> str:
    """基于用户偏好向量，推荐向量空间中最近邻的美甲款式。

    Args:
        user_id: 用户唯一标识。
        top_k: 返回推荐数量，默认 5。

    Returns:
        {"recommendations": [{"style_id","description","category","image_path","similarity"}],
         "count": n, "message": "..."}
    """
    try:
        # 1. 获取用户偏好向量
        with get_db() as conn:
            row = conn.execute(
                "SELECT pref_vector FROM nail_user_prefs WHERE user_id=?", (user_id,)
            ).fetchone()

        if row is None:
            return _cold_start_recommend(top_k)

        pref_vec = json.loads(row["pref_vector"])
        col = _get_nail_styles_collection()

        if col.count() == 0:
            return _cold_start_recommend(top_k)

        # 2. 用偏好向量查最近邻
        results = col.query(
            query_embeddings=[pref_vec],
            n_results=min(top_k + 5, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        docs  = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        # 3. 过滤已试戴款式（最近10次）
        with get_db() as conn:
            tried_rows = conn.execute(
                "SELECT DISTINCT style_id FROM ops_signals WHERE user_id=? ORDER BY id DESC LIMIT 10",
                (user_id,)
            ).fetchall()
        tried = {r["style_id"] for r in tried_rows}

        recs = [
            {
                "style_id":   m.get("style_id", ""),
                "description": doc,
                "category":   m.get("category", ""),
                "image_path": m.get("image_path", ""),
                "similarity": round(max(0.0, 1.0 - float(d)), 3),
            }
            for doc, m, d in zip(docs, metas, dists)
            if m.get("style_id") not in tried
        ][:top_k]

        return json.dumps({
            "recommendations": recs,
            "count": len(recs),
            "message": f"基于您的偏好推荐 {len(recs)} 款",
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("NailStyleRecommend failed: %s", e)
        return _cold_start_recommend(top_k)
```

- [ ] **Step 3: 创建冷启动脚本 `backend/scripts/init_nail_styles.py`**

```python
#!/usr/bin/env python3
"""
冷启动脚本：将 data/mock/nail_styles/ 目录下的款式描述批量嵌入 ChromaDB nail_styles collection。
用法：cd backend && uv run python scripts/init_nail_styles.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent.parent))  # 项目根目录

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
STYLES_DIR = Path("data/mock/nail_styles")

# 内置款式库（无外部文件时使用）
BUILTIN_STYLES = [
    {"style_id": "french-001", "description": "经典法式美甲，白色甲尖，粉嫩底色，干净优雅", "category": "法式", "color_tags": "white,pink", "image_path": ""},
    {"style_id": "gradient-001", "description": "渐变美甲，从深粉到浅紫的柔和过渡，梦幻少女风", "category": "渐变", "color_tags": "pink,purple", "image_path": ""},
    {"style_id": "solid-red-001", "description": "纯色红色美甲，高饱和正红，气场十足", "category": "纯色", "color_tags": "red", "image_path": ""},
    {"style_id": "floral-001", "description": "碎花美甲，白底小碎花图案，清新田园风", "category": "花纹", "color_tags": "white,green,pink", "image_path": ""},
    {"style_id": "glitter-001", "description": "闪粉美甲，金色细闪粉，节日感十足", "category": "闪粉", "color_tags": "gold", "image_path": ""},
    {"style_id": "minimalist-001", "description": "简约线条美甲，白底细黑线，极简现代风", "category": "简约", "color_tags": "white,black", "image_path": ""},
    {"style_id": "dark-001", "description": "暗色系美甲，深酒红色，神秘性感", "category": "暗色", "color_tags": "dark_red,burgundy", "image_path": ""},
    {"style_id": "nude-001", "description": "裸色美甲，接近肤色的米白，百搭日常", "category": "裸色", "color_tags": "nude,beige", "image_path": ""},
    {"style_id": "blue-001", "description": "蓝色系美甲，海军蓝底色，夏日清爽感", "category": "纯色", "color_tags": "blue,navy", "image_path": ""},
    {"style_id": "art-001", "description": "艺术美甲，手绘抽象图案，独一无二", "category": "艺术", "color_tags": "multicolor", "image_path": ""},
]


def main():
    import chromadb
    from chromadb.utils import embedding_functions

    print(f"初始化 ChromaDB nail_styles collection at {CHROMA_DIR}")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    ef = embedding_functions.DefaultEmbeddingFunction()
    col = client.get_or_create_collection("nail_styles", embedding_function=ef)

    # 读取外部款式文件（若存在）
    styles = list(BUILTIN_STYLES)
    if STYLES_DIR.exists():
        for f in STYLES_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    styles.extend(data)
                elif isinstance(data, dict):
                    styles.append(data)
            except Exception as e:
                print(f"  跳过 {f.name}: {e}")

    # 过滤已存在的
    existing_ids = set(col.get(ids=[s["style_id"] for s in styles])["ids"])
    to_add = [s for s in styles if s["style_id"] not in existing_ids]

    if not to_add:
        print(f"所有 {len(styles)} 个款式已存在，无需重新导入")
        return

    col.add(
        documents=[s["description"] for s in to_add],
        metadatas=[{
            "style_id":   s["style_id"],
            "category":   s.get("category", ""),
            "color_tags": s.get("color_tags", ""),
            "image_path": s.get("image_path", ""),
            "source":     "static",
        } for s in to_add],
        ids=[s["style_id"] for s in to_add],
    )
    print(f"✅ 成功导入 {len(to_add)} 个款式（总计 {col.count()} 个）")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行冷启动脚本**

```bash
cd /path/to/hackathon-meituan-ai/backend
uv run python scripts/init_nail_styles.py
```

期望输出：`✅ 成功导入 10 个款式（总计 10 个）`

- [ ] **Step 5: 验证 nail_style_recommend_tool 降级路径**

```bash
cd /path/to/hackathon-meituan-ai/backend
uv run python -c "
import sys, os
sys.path.insert(0, '.')
os.chdir('..')
from backend.packages.harness.deerflow.tools.nail.nail_style_recommend import nail_style_recommend_tool
result = nail_style_recommend_tool.invoke({'user_id': 'test-user-no-pref', 'top_k': 3})
import json; data = json.loads(result)
print('count:', data.get('count'), 'message:', data.get('message'))
"
```

期望输出：count 为 0-3 之间的数，message 包含"推荐"

---

## Task 5: 新增工具 user_pref_analytics + nail_run_query

**Files:**
- Create: `backend/packages/harness/deerflow/tools/nail/user_pref_analytics.py`
- Create: `backend/packages/harness/deerflow/tools/nail/nail_run_query.py`

- [ ] **Step 1: 创建 `user_pref_analytics.py`**

```python
# backend/packages/harness/deerflow/tools/nail/user_pref_analytics.py
"""聚合分析全体用户偏好分布，识别主要风格群体。"""
import json
import logging

from langchain.tools import tool

from .base import get_db

logger = logging.getLogger(__name__)


@tool
def user_pref_analytics_tool(top_k_styles: int = 10) -> str:
    """聚合分析全体用户的偏好数据，返回热门款式和偏好风格分布。

    Args:
        top_k_styles: 返回热门款式数量，默认 10。

    Returns:
        {"total_users": n, "top_styles": [...], "signal_summary": {...}, "message": "..."}
    """
    try:
        with get_db() as conn:
            # 热门款式（按收藏+试戴信号排名）
            top_styles = conn.execute("""
                SELECT style_id,
                       SUM(CASE WHEN signal_type='save'  THEN 3 ELSE 1 END) as score,
                       COUNT(*) as total_signals,
                       SUM(CASE WHEN signal_type='save'  THEN 1 ELSE 0 END) as saves,
                       SUM(CASE WHEN signal_type='order' THEN 1 ELSE 0 END) as orders,
                       SUM(CASE WHEN signal_type='click' THEN 1 ELSE 0 END) as clicks
                FROM ops_signals
                GROUP BY style_id
                ORDER BY score DESC
                LIMIT ?
            """, (top_k_styles,)).fetchall()

            # 用户数
            user_count = conn.execute(
                "SELECT COUNT(DISTINCT user_id) as cnt FROM nail_user_prefs"
            ).fetchone()

            # 最近7天信号汇总
            signal_summary = conn.execute("""
                SELECT signal_type, COUNT(*) as cnt
                FROM ops_signals
                WHERE created_at >= datetime('now', '-7 days')
                GROUP BY signal_type
            """).fetchall()

        top_styles_data = [
            {
                "style_id": r["style_id"],
                "score": r["score"],
                "saves": r["saves"],
                "orders": r["orders"],
                "clicks": r["clicks"],
            }
            for r in top_styles
        ]

        signal_data = {r["signal_type"]: r["cnt"] for r in signal_summary}

        return json.dumps({
            "total_users": user_count["cnt"] if user_count else 0,
            "top_styles": top_styles_data,
            "signal_summary_7d": signal_data,
            "message": f"分析了 {user_count['cnt'] if user_count else 0} 名用户的偏好数据",
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("UserPrefAnalytics failed: %s", e)
        return json.dumps({"total_users": 0, "top_styles": [], "error": str(e)})
```

- [ ] **Step 2: 创建 `nail_run_query.py`**

```python
# backend/packages/harness/deerflow/tools/nail/nail_run_query.py
"""查询试戴执行数据：工具调用链、Agent 思考过程、时间统计。"""
import json
import logging

from langchain.tools import tool

from .base import get_db

logger = logging.getLogger(__name__)


@tool
def nail_run_query_tool(user_id: str = "", limit: int = 3) -> str:
    """查询最近 N 次 AI 试戴的完整执行数据，包含工具调用链和思考过程。

    Args:
        user_id: 过滤指定用户的记录（空字符串则返回全局最近记录）。
        limit: 返回条数，默认 3，最大 10。

    Returns:
        {
            "runs": [
                {
                    "run_id": "...",
                    "nail_role": "...",
                    "status": "...",
                    "created_at": "...",
                    "total_duration_ms": 18420,
                    "tool_chain": [
                        {"tool": "hand_detect_tool", "duration_ms": 320, "success": true, "call_index": 0}
                    ],
                    "thinking_log": ["检测到手部关键点...", ...],
                    "tool_count": 6
                }
            ],
            "count": n
        }
    """
    try:
        limit = min(int(limit), 10)

        with get_db() as conn:
            # 查询 nail_runs
            if user_id:
                runs = conn.execute(
                    "SELECT id, nail_role, status, created_at FROM nail_runs "
                    "WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit)
                ).fetchall()
            else:
                runs = conn.execute(
                    "SELECT id, nail_role, status, created_at FROM nail_runs "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()

            result_runs = []
            for run in runs:
                run_id = run["id"]

                # 查询该 run 的工具调用链
                calls = conn.execute(
                    "SELECT tool_name, call_index, duration_ms, thinking, output_json "
                    "FROM tool_call_log WHERE run_id=? ORDER BY call_index ASC",
                    (run_id,)
                ).fetchall()

                tool_chain = []
                thinking_log = []
                total_ms = 0

                for call in calls:
                    duration = call["duration_ms"] or 0
                    total_ms += max(0, duration)
                    tool_chain.append({
                        "tool":        call["tool_name"],
                        "call_index":  call["call_index"],
                        "duration_ms": duration,
                        "success":     duration >= 0,
                    })
                    if call["thinking"]:
                        thinking_log.append(call["thinking"])

                result_runs.append({
                    "run_id":           run_id,
                    "nail_role":        run["nail_role"],
                    "status":           run["status"],
                    "created_at":       run["created_at"],
                    "total_duration_ms": total_ms,
                    "tool_chain":       tool_chain,
                    "thinking_log":     thinking_log,
                    "tool_count":       len(tool_chain),
                })

        return json.dumps({"runs": result_runs, "count": len(result_runs)}, ensure_ascii=False)

    except Exception as e:
        logger.error("NailRunQuery failed: %s", e)
        return json.dumps({"runs": [], "count": 0, "error": str(e)})
```

- [ ] **Step 3: 验证两个工具可以导入**

```bash
cd /path/to/hackathon-meituan-ai/backend
uv run python -c "
from packages.harness.deerflow.tools.nail.user_pref_analytics import user_pref_analytics_tool
from packages.harness.deerflow.tools.nail.nail_run_query import nail_run_query_tool
print('imports OK')
"
```

期望输出：`imports OK`

---

## Task 6: tool_call_log 写入中间件

**Files:**
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/agent.py`

- [ ] **Step 1: 在 `agent.py` 顶部导入区添加**

在已有 `import` 语句末尾追加：

```python
import time as _time
import uuid as _uuid
```

- [ ] **Step 2: 在 `agent.py` 中添加 `_log_tool_call` 函数**

在 `_get_runtime_config` 函数之前（文件开头的辅助函数区），添加：

```python
def _log_tool_call(
    run_id: str,
    tool_name: str,
    call_index: int,
    input_data: object,
    output_data: object,
    thinking: str,
    duration_ms: int,
) -> None:
    """幂等写入工具调用日志到 tool_call_log 表，失败不影响主流程。"""
    try:
        import json as _json
        from packages.harness.deerflow.tools.nail.base import get_db as _nail_get_db
        with _nail_get_db() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO tool_call_log "
                "(id, run_id, tool_name, call_index, input_json, output_json, thinking, duration_ms) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    str(_uuid.uuid4()),
                    run_id,
                    tool_name,
                    call_index,
                    _json.dumps(input_data, ensure_ascii=False, default=str)[:4096],
                    _json.dumps(output_data, ensure_ascii=False, default=str)[:4096],
                    str(thinking or "")[:2048],
                    duration_ms,
                )
            )
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).debug("_log_tool_call failed: %s", _e)
```

- [ ] **Step 3: 在工具执行节点注入日志**

在 `agent.py` 中找到 `create_agent(` 调用处，在 `tools=...` 列表传入之前，包装一个计时日志闭包。在 `_effective_groups` 构建和 `tools = get_available_tools(...)` 行之后，添加：

```python
    # NailFlow: wrap tools with call_index counter + tool_call_log
    _run_id_for_log = str(_uuid.uuid4())
    _call_counter: list[int] = [0]

    def _wrap_tool(t):
        original_func = t.func if hasattr(t, 'func') else None
        if original_func is None:
            return t
        import functools

        @functools.wraps(original_func)
        def _wrapped(*args, **kwargs):
            idx = _call_counter[0]
            _call_counter[0] += 1
            start = _time.monotonic()
            result = None
            try:
                result = original_func(*args, **kwargs)
                duration = int((_time.monotonic() - start) * 1000)
                _log_tool_call(_run_id_for_log, t.name, idx,
                               {"args": args, "kwargs": kwargs}, result, "", duration)
                return result
            except Exception as exc:
                duration = int((_time.monotonic() - start) * 1000)
                _log_tool_call(_run_id_for_log, t.name, idx,
                               {"args": args, "kwargs": kwargs}, {"error": str(exc)}, "", -1)
                raise

        t.func = _wrapped
        return t

    tools = [_wrap_tool(t) for t in tools]
```

> **注意**：DeerFlow 的工具封装较深，`.func` 属性不一定存在。如果包装失败（`original_func is None`），直接返回原工具，不影响正常执行。

- [ ] **Step 4: 验证后端正常启动**

```bash
cd /path/to/hackathon-meituan-ai/backend
uv run python -m uvicorn app.gateway.app:app --port 8001 --reload &
sleep 5
curl -s http://localhost:8001/health
```

期望输出：`{"status":"healthy","service":"deer-flow-gateway"}`

---

## Task 7: 运营/收藏 API 扩展

**Files:**
- Modify: `backend/app/gateway/routers/nail_ops.py`

- [ ] **Step 1: 新增 `POST /api/nail/styles/{style_id}/save` 端点**

在 `nail_ops.py` 末尾添加：

```python
class SaveStyleRequest(BaseModel):
    signal_type: str = "save"  # "save" 或 "search"


@router.post("/api/nail/styles/{style_id}/save")
@require_auth
async def save_style(style_id: str, body: SaveStyleRequest, request: Request):
    """用户收藏款式：写入偏好向量 + ops_signals。"""
    from packages.harness.deerflow.tools.nail.base import update_user_pref_vector, get_db
    user = request.state.user
    user_id = str(user.id)

    signal_type = body.signal_type if body.signal_type in ("save", "search") else "save"
    update_user_pref_vector(user_id, style_id, signal_type)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO ops_signals (user_id, style_id, signal_type) VALUES (?,?,?)",
            (user_id, style_id, signal_type)
        )
    return {"saved": True, "style_id": style_id, "signal_type": signal_type}
```

- [ ] **Step 2: 新增 `GET /api/nail/analytics/pref-distribution` 端点**

```python
@router.get("/api/nail/analytics/pref-distribution")
@require_auth
async def get_pref_distribution(request: Request):
    """返回全体用户偏好风格分布（供运营看板饼图使用）。"""
    from packages.harness.deerflow.tools.nail.base import get_db
    with get_db() as conn:
        rows = conn.execute("""
            SELECT s.style_id,
                   COALESCE(c.category, '其他') as category,
                   SUM(CASE WHEN s.signal_type='save'  THEN 3 ELSE 1 END) as score
            FROM ops_signals s
            LEFT JOIN nail_style_catalog c ON s.style_id = c.style_id
            GROUP BY s.style_id, c.category
            ORDER BY score DESC
        """).fetchall()

    # 按 category 聚合
    cat_scores: dict[str, int] = {}
    for r in rows:
        cat = r["category"] or "其他"
        cat_scores[cat] = cat_scores.get(cat, 0) + r["score"]

    total = sum(cat_scores.values()) or 1
    distribution = [
        {"category": k, "score": v, "percentage": round(v / total * 100, 1)}
        for k, v in sorted(cat_scores.items(), key=lambda x: -x[1])
    ]
    return {"distribution": distribution, "total_signals": sum(cat_scores.values())}
```

- [ ] **Step 3: 扩展现有 `GET /api/nail/dashboard` 返回 top_styles**

在现有 `get_dashboard()` 函数中，在返回值里追加 `top_styles` 字段：

```python
        top_styles = conn.execute("""
            SELECT style_id, COUNT(*) as total,
                   SUM(CASE WHEN signal_type='save' THEN 1 ELSE 0 END) as saves
            FROM ops_signals
            WHERE created_at >= datetime('now', ? || ' days')
            GROUP BY style_id
            ORDER BY total DESC
            LIMIT 10
        """, (f"-{days}",)).fetchall()
```

在 return 里加 `"top_styles": [dict(r) for r in top_styles]`。

- [ ] **Step 4: 新增 `GET /api/nail/analytics/latest-run` 端点（供评分面板 ToolTimeline 使用）**

```python
@router.get("/api/nail/analytics/latest-run")
@require_auth
async def get_latest_run(request: Request):
    """返回最近一次 nail_run 的工具调用链数据，供前端 ToolTimeline 展示。"""
    from packages.harness.deerflow.tools.nail.base import get_db
    user = request.state.user
    with get_db() as conn:
        run = conn.execute(
            "SELECT id, nail_role, status, created_at FROM nail_runs "
            "WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (str(user.id),)
        ).fetchone()
        if run is None:
            return {"run": None}
        calls = conn.execute(
            "SELECT tool_name, call_index, duration_ms FROM tool_call_log "
            "WHERE run_id=? ORDER BY call_index ASC",
            (run["id"],)
        ).fetchall()
    tool_chain = [
        {
            "tool":        c["tool_name"],
            "call_index":  c["call_index"],
            "duration_ms": c["duration_ms"] or 0,
            "success":     (c["duration_ms"] or 0) >= 0,
        }
        for c in calls
    ]
    total_ms = sum(max(0, c["duration_ms"] or 0) for c in calls)
    return {
        "run": {
            "run_id":            run["id"],
            "tool_chain":        tool_chain,
            "total_duration_ms": total_ms,
        }
    }
```

- [ ] **Step 5: 验证新端点**

```bash
curl -s -X POST http://localhost:8001/api/nail/styles/french-001/save \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(curl -s -X POST http://localhost:8001/api/auth/login -H 'Content-Type: application/json' -d '{"email":"ops@nailflow.dev","password":"nail123456"}' | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')" \
  -d '{"signal_type":"save"}'
```

期望输出：`{"saved":true,...}`

---

## Task 8: 前端 useNailThread + NailChatPane

**Files:**
- Create: `frontend/src/core/nail-chat/use-nail-thread.ts`
- Create: `frontend/src/core/nail-chat/use-nail-chat.ts`
- Create: `frontend/src/core/nail-chat/index.ts`
- Create: `frontend/src/components/nail/nail-chat-pane.tsx`

- [ ] **Step 1: 创建 `use-nail-thread.ts`**

```typescript
// frontend/src/core/nail-chat/use-nail-thread.ts
"use client";

import { useCallback, useState } from "react";
import { useAuth } from "@/core/auth/AuthProvider";

export type NailPageMode = "tryon" | "ops" | "eval";

export function useNailThread(pageMode: NailPageMode) {
  const { user } = useAuth();
  const userId = (user as any)?.id ?? "anon";
  const storageKey = `nail_thread_${pageMode}_${userId}`;

  const [threadId, setThreadId] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(storageKey) ?? "";
  });

  const ensureThread = useCallback(async (): Promise<string> => {
    if (threadId) return threadId;
    const res = await fetch("/api/v1/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!res.ok) throw new Error(`创建 thread 失败: ${res.status}`);
    const data = await res.json();
    const id: string = data.thread_id ?? data.id ?? "";
    if (id) {
      localStorage.setItem(storageKey, id);
      setThreadId(id);
    }
    return id;
  }, [threadId, storageKey]);

  const resetThread = useCallback(() => {
    localStorage.removeItem(storageKey);
    setThreadId("");
  }, [storageKey]);

  return { threadId, ensureThread, resetThread };
}
```

- [ ] **Step 2: 创建 `use-nail-chat.ts`**

```typescript
// frontend/src/core/nail-chat/use-nail-chat.ts
"use client";

import { useCallback, useRef, useState } from "react";
import { useAuth } from "@/core/auth/AuthProvider";
import type { NailPageMode } from "./use-nail-thread";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export function useNailChat(
  pageMode: NailPageMode,
  ensureThread: () => Promise<string>,
  extraConfig?: Record<string, unknown>,
) {
  const { user } = useAuth();
  const nailRole = (user as any)?.nail_role ?? "user";
  const selectedModel = (user as any)?.selectedModel ?? undefined;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;
      setError("");

      // 先追加用户消息
      const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content };
      setMessages((prev) => [...prev, userMsg]);

      // 追加流式助手消息占位
      const assistantId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        { id: assistantId, role: "assistant", content: "", isStreaming: true },
      ]);
      setIsLoading(true);

      try {
        const threadId = await ensureThread();
        abortRef.current = new AbortController();

        const res = await fetch(`/api/v1/threads/${threadId}/runs/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: abortRef.current.signal,
          body: JSON.stringify({
            input: {
              messages: [{ role: "user", content }],
            },
            config: {
              configurable: {
                nail_role: nailRole,
                nail_page_mode: pageMode,
                ...(selectedModel ? { model_name: selectedModel } : {}),
                ...extraConfig,
              },
            },
          }),
        });

        if (!res.ok) throw new Error(`运行失败: ${res.status}`);

        // 读取 SSE 流
        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let accumulated = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6));
              const text: string =
                data?.content ??
                data?.text ??
                (typeof data === "string" ? data : "");
              if (text) {
                accumulated += text;
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: accumulated }
                      : m,
                  ),
                );
              }
              // 工具调用完成时触发面板刷新
              if (data?.type === "tool_result" && typeof window !== "undefined") {
                window.dispatchEvent(new CustomEvent("nail:refresh-dashboard"));
              }
            } catch {
              // 忽略非 JSON 行（心跳等）
            }
          }
        }

        // 标记流式完成
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false } : m,
          ),
        );
      } catch (e: unknown) {
        if ((e as Error)?.name === "AbortError") return;
        const msg = (e as Error)?.message ?? "请求失败";
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `❌ ${msg}`, isStreaming: false }
              : m,
          ),
        );
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, ensureThread, nailRole, pageMode, selectedModel, extraConfig],
  );

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    setIsLoading(false);
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)),
    );
  }, []);

  const clearMessages = useCallback(() => setMessages([]), []);

  return { messages, isLoading, error, sendMessage, stopStream, clearMessages };
}
```

- [ ] **Step 3: 创建 `index.ts` 导出**

```typescript
// frontend/src/core/nail-chat/index.ts
export { useNailThread } from "./use-nail-thread";
export { useNailChat } from "./use-nail-chat";
export type { ChatMessage, NailPageMode } from "./use-nail-thread";
```

注意：`NailPageMode` 从 `use-nail-thread.ts` 导出，`ChatMessage` 从 `use-nail-chat.ts` 导出，在 `index.ts` 统一 re-export：

```typescript
// frontend/src/core/nail-chat/index.ts
export { useNailThread, type NailPageMode } from "./use-nail-thread";
export { useNailChat, type ChatMessage } from "./use-nail-chat";
```

- [ ] **Step 4: 创建 `nail-chat-pane.tsx`**

```tsx
// frontend/src/components/nail/nail-chat-pane.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useNailChat, type ChatMessage, type NailPageMode } from "@/core/nail-chat";
import { useQuery } from "@tanstack/react-query";

interface PageModeConfig {
  title: string;
  subtitle: string;
  suggestions: string[];
}

async function fetchPageModeConfig(mode: string): Promise<PageModeConfig> {
  const res = await fetch(`/api/nail/config/page-mode/${mode}`);
  if (!res.ok) throw new Error("Failed to load page mode config");
  return res.json();
}

interface NailChatPaneProps {
  pageMode: NailPageMode;
  ensureThread: () => Promise<string>;
  resetThread: () => void;
  extraConfig?: Record<string, unknown>;
  className?: string;
}

export function NailChatPane({
  pageMode,
  ensureThread,
  resetThread,
  extraConfig,
  className,
}: NailChatPaneProps) {
  const { messages, isLoading, error, sendMessage, stopStream, clearMessages } =
    useNailChat(pageMode, ensureThread, extraConfig);

  const { data: modeConfig } = useQuery({
    queryKey: ["nail-page-mode", pageMode],
    queryFn: () => fetchPageModeConfig(pageMode),
    staleTime: Infinity,
  });

  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={cn("flex h-full flex-col bg-background", className)}>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-2">
        <div>
          <p className="text-sm font-semibold">{modeConfig?.title ?? "AI 分析"}</p>
          <p className="text-xs text-muted-foreground">{modeConfig?.subtitle ?? ""}</p>
        </div>
        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => { clearMessages(); resetThread(); }}
          >
            重置
          </Button>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 px-4 py-3" ref={scrollRef as any}>
        {messages.length === 0 && modeConfig?.suggestions && (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground mb-3">试试这些问题：</p>
            {modeConfig.suggestions.map((s) => (
              <button
                key={s}
                onClick={() => sendMessage(s)}
                className="w-full rounded-lg border px-3 py-2 text-left text-xs hover:bg-accent transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="space-y-3">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
        </div>

        {error && (
          <div className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
            {error}
          </div>
        )}
      </ScrollArea>

      {/* Input */}
      <div className="border-t p-3">
        <div className="flex gap-2">
          <textarea
            className="flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            rows={2}
            placeholder="输入消息…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <div className="flex flex-col gap-1">
            {isLoading ? (
              <Button size="sm" variant="outline" onClick={stopStream} className="h-full text-xs">
                停止
              </Button>
            ) : (
              <Button size="sm" onClick={handleSend} className="h-full text-xs" disabled={!input.trim()}>
                发送
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3 py-2 text-sm",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground",
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.content}</p>
        {message.isStreaming && (
          <span className="ml-1 inline-block h-3 w-1 animate-pulse bg-current opacity-70" />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 验证前端编译无报错**

```bash
cd /path/to/hackathon-meituan-ai/frontend
pnpm tsc --noEmit 2>&1 | head -20
```

期望输出：无错误（或只有与本 Task 无关的已有错误）

---

## Task 9: NailPageLayout C 布局通用组件

**Files:**
- Create: `frontend/src/components/nail/nail-page-layout.tsx`

- [ ] **Step 1: 创建 `nail-page-layout.tsx`**

```tsx
// frontend/src/components/nail/nail-page-layout.tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BotIcon, XIcon } from "lucide-react";
import { NailChatPane } from "./nail-chat-pane";
import { useNailThread, type NailPageMode } from "@/core/nail-chat";

interface NailPageLayoutProps {
  pageMode: NailPageMode;
  /** 左侧数据面板内容 */
  panel: React.ReactNode;
  /** 额外的 configurable 参数传给 Agent */
  extraConfig?: Record<string, unknown>;
  className?: string;
}

export function NailPageLayout({
  pageMode,
  panel,
  extraConfig,
  className,
}: NailPageLayoutProps) {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { threadId, ensureThread, resetThread } = useNailThread(pageMode);

  return (
    <div className={cn("flex h-full flex-col overflow-hidden", className)}>
      {/* AI 分析按钮（固定在右下角） */}
      <div className="absolute bottom-6 right-6 z-20">
        {!isChatOpen && (
          <Button
            onClick={() => setIsChatOpen(true)}
            className="h-11 gap-2 rounded-full shadow-lg"
          >
            <BotIcon className="size-4" />
            AI 分析
          </Button>
        )}
      </div>

      <div className="relative flex min-h-0 flex-1">
        {/* 左侧：数据面板 */}
        <div
          className={cn(
            "min-h-0 overflow-auto transition-all duration-300",
            isChatOpen ? "w-[60%]" : "w-full",
          )}
        >
          {panel}
        </div>

        {/* 右侧：Chat 面板（滑入） */}
        <div
          className={cn(
            "flex flex-col border-l bg-background transition-all duration-300",
            isChatOpen ? "w-[40%]" : "w-0 overflow-hidden",
          )}
        >
          {isChatOpen && (
            <>
              <div className="flex items-center justify-end border-b px-2 py-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  onClick={() => setIsChatOpen(false)}
                >
                  <XIcon className="size-4" />
                </Button>
              </div>
              <div className="min-h-0 flex-1 overflow-hidden">
                <NailChatPane
                  pageMode={pageMode}
                  ensureThread={ensureThread}
                  resetThread={resetThread}
                  extraConfig={extraConfig}
                  className="h-full"
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 验证编译**

```bash
cd /path/to/hackathon-meituan-ai/frontend
pnpm tsc --noEmit 2>&1 | grep "nail-page-layout"
```

期望输出：无错误

---

## Task 10: 运营看板页面改造

**Files:**
- Modify: `frontend/src/app/workspace/nail/dashboard/page.tsx`

- [ ] **Step 1: 在文件顶部追加新 imports**

在已有 import 区末尾追加：

```tsx
import { NailPageLayout } from "@/components/nail/nail-page-layout";
import { useEffect } from "react";
```

- [ ] **Step 2: 在 `fetchData` useCallback 外包 useEffect 监听刷新事件**

在 `useEffect(() => { if (canAccess...) fetchData(); }, ...)` 之后追加：

```tsx
  // 监听 Agent 工具调用完成后的刷新信号
  useEffect(() => {
    const handler = () => fetchData(true);
    window.addEventListener("nail:refresh-dashboard", handler);
    return () => window.removeEventListener("nail:refresh-dashboard", handler);
  }, [fetchData]);
```

- [ ] **Step 3: 将现有 return JSX 包进 NailPageLayout**

找到 `return (` 的最顶层 JSX，将整个现有 JSX 包裹为 `<NailPageLayout>` 的 `panel` prop：

```tsx
  const panelContent = (
    <div className="h-full overflow-auto">
      {/* 原有 JSX 内容原样复制到此处 */}
      {/* 即原来 return ( ... ) 里面的全部内容 */}
    </div>
  );

  return (
    <NailPageLayout
      pageMode="ops"
      panel={panelContent}
    />
  );
```

- [ ] **Step 4: 验证运营看板页面可以访问**

在浏览器访问 `http://localhost:3000/workspace/nail/dashboard`，确认：
1. 右下角有「🤖 AI 分析」按钮
2. 点击后右侧滑入 chat 面板
3. chat 面板显示「运营分析助手」标题和建议问题

---

## Task 11: 评分面板改造 + 工具时序图

**Files:**
- Create: `frontend/src/components/nail/tool-timeline.tsx`
- Modify: `frontend/src/app/workspace/nail/evaluation/page.tsx`

- [ ] **Step 1: 创建 `tool-timeline.tsx`**

```tsx
// frontend/src/components/nail/tool-timeline.tsx
"use client";

import { cn } from "@/lib/utils";

interface ToolCall {
  tool: string;
  call_index: number;
  duration_ms: number;
  success: boolean;
}

interface ToolTimelineProps {
  toolChain: ToolCall[];
  totalDurationMs: number;
  className?: string;
}

const TOOL_EMOJI: Record<string, string> = {
  hand_detect_tool:         "🖐",
  nail_mask_tool:           "✂️",
  style_understanding_tool: "🎨",
  prompt_builder_tool:      "📝",
  image_generation_tool:    "🖼️",
  quality_check_tool:       "✅",
  evaluation_tool:          "📊",
  trend_query_tool:         "📈",
  ops_analysis_tool:        "💡",
};

export function ToolTimeline({ toolChain, totalDurationMs, className }: ToolTimelineProps) {
  if (!toolChain || toolChain.length === 0) {
    return (
      <div className={cn("rounded-lg border bg-muted/30 p-4 text-center text-xs text-muted-foreground", className)}>
        暂无工具调用记录
      </div>
    );
  }

  const maxDuration = Math.max(...toolChain.map((t) => Math.abs(t.duration_ms)), 1);

  return (
    <div className={cn("rounded-lg border bg-card p-3 space-y-1.5", className)}>
      <p className="text-xs font-semibold text-muted-foreground mb-2">工具调用时序</p>
      {toolChain.map((call) => {
        const pct = Math.min((Math.abs(call.duration_ms) / maxDuration) * 100, 100);
        const label = call.tool.replace("_tool", "").replace(/_/g, " ");
        const emoji = TOOL_EMOJI[call.tool] ?? "⚙️";
        const msText = call.duration_ms < 0
          ? "失败"
          : call.duration_ms >= 1000
            ? `${(call.duration_ms / 1000).toFixed(1)}s`
            : `${call.duration_ms}ms`;

        return (
          <div key={call.call_index} className="flex items-center gap-2">
            <span className="w-5 text-base">{emoji}</span>
            <span className="w-28 truncate text-xs text-foreground/80">{label}</span>
            <div className="relative h-4 flex-1 rounded-sm bg-muted overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-sm transition-all",
                  call.success ? "bg-primary/60" : "bg-destructive/60",
                )}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className={cn("w-14 text-right text-xs tabular-nums",
              call.success ? "text-muted-foreground" : "text-destructive")}>
              {msText}
            </span>
            <span className="text-xs">{call.success ? "✓" : "✗"}</span>
          </div>
        );
      })}
      <div className="border-t pt-1.5 flex justify-between text-xs text-muted-foreground">
        <span>{toolChain.length} 个工具</span>
        <span>
          总计 {totalDurationMs >= 1000
            ? `${(totalDurationMs / 1000).toFixed(1)}s`
            : `${totalDurationMs}ms`}
          {toolChain.every((t) => t.success) ? " ✓ 全部成功" : " ⚠️ 有失败"}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 修改 `evaluation/page.tsx` 引入 NailPageLayout 和 ToolTimeline**

在 import 区追加：

```tsx
import { NailPageLayout } from "@/components/nail/nail-page-layout";
import { ToolTimeline } from "@/components/nail/tool-timeline";
import { useCallback, useEffect, useState } from "react";
```

- [ ] **Step 3: 添加加载工具调用数据的 state 和 fetch**

在已有 state 之后添加：

```tsx
  interface RunData {
    run_id: string;
    tool_chain: Array<{ tool: string; call_index: number; duration_ms: number; success: boolean }>;
    total_duration_ms: number;
  }
  const [latestRun, setLatestRun] = useState<RunData | null>(null);

  const fetchLatestRun = useCallback(() => {
    fetch("/api/nail/analytics/latest-run")
      .then((r) => r.json())
      .then((d) => setLatestRun(d.run ?? null))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchLatestRun();
    const handler = () => fetchLatestRun();
    window.addEventListener("nail:refresh-dashboard", handler);
    return () => window.removeEventListener("nail:refresh-dashboard", handler);
  }, [fetchLatestRun]);
```

> **备注**：`/api/nail/analytics/latest-run` 端点可以在 `nail_ops.py` 中快速新增：查询最近一条 `nail_runs` + 对应 `tool_call_log`。如果暂时没有数据，`ToolTimeline` 会显示"暂无工具调用记录"，不影响页面功能。

- [ ] **Step 4: 将现有 JSX 包进 NailPageLayout**

在现有评分面板 JSX 末尾（`ScoreRing` + rubric 条形图 + 问题列表之后）追加 `ToolTimeline`，然后将全部内容包进 `NailPageLayout`：

```tsx
  const panelContent = (
    <div className="h-full overflow-auto p-4 space-y-4">
      {/* 原有评分内容（保持不变）*/}
      {/* ... 原来的 ScoreRing、rubric、blocking_issues、next_dev_tasks ... */}

      {/* 新增：工具调用时序图 */}
      {latestRun && (
        <ToolTimeline
          toolChain={latestRun.tool_chain}
          totalDurationMs={latestRun.total_duration_ms}
        />
      )}
    </div>
  );

  return (
    <NailPageLayout
      pageMode="eval"
      panel={panelContent}
    />
  );
```

- [ ] **Step 5: 验证评分面板页面**

访问 `http://localhost:3000/workspace/nail/evaluation`，确认：
1. 右下角有「🤖 AI 分析」按钮
2. 点击后右侧滑入 chat 面板，显示「评分分析助手」
3. 建议问题可点击发送

---

## Task 12: 工具管理 enabled_pages 开关 + config.yaml

**Files:**
- Modify: `frontend/src/components/nail/tool-card.tsx`
- Modify: `backend/config.yaml`

- [ ] **Step 1: 修改 `tool-card.tsx`，新增 enabled_pages 开关行**

在文件中找到工具卡片的开关（`Switch` 控制 `is_enabled`）之后，追加页面启用行：

首先确保 `ToolInfo` 类型包含 `enabled_pages`（在 `frontend/src/core/nail-models/types.ts` 中）：

```typescript
// 在 ToolInfo interface 中追加
enabled_pages?: string[];
```

然后在 `tool-card.tsx` 中，在 Switch 行之后添加：

```tsx
{/* 页面启用开关 */}
{tool.is_llm && tool.is_enabled && (
  <div className="mt-2 flex items-center gap-3 border-t pt-2">
    <span className="text-xs text-muted-foreground w-12">页面</span>
    <div className="flex gap-2">
      {(["tryon", "ops", "eval"] as const).map((mode) => {
        const LABELS = { tryon: "试戴", ops: "运营", eval: "评分" };
        const isEnabled = tool.enabled_pages?.includes(mode) ?? true;
        return (
          <label key={mode} className="flex cursor-pointer items-center gap-1">
            <input
              type="checkbox"
              className="size-3 rounded"
              checked={isEnabled}
              onChange={() => {
                const current = tool.enabled_pages ?? ["tryon", "ops", "eval"];
                const next = isEnabled
                  ? current.filter((p) => p !== mode)
                  : [...current, mode];
                updateTool({ toolName: tool.name, enabled_pages: next });
              }}
            />
            <span className="text-xs">{LABELS[mode]}</span>
          </label>
        );
      })}
    </div>
  </div>
)}
```

需要在 `useUpdateTool` mutation 中加入 `enabled_pages` 参数，确保 `ToolUpdateRequest` 包含该字段（Task 3 已处理后端）。

- [ ] **Step 2: 在 `config.yaml` 注册 3 个新工具**

打开 `config.yaml`，在 `tools:` 列表末尾（已有13个工具之后）追加：

```yaml
  - name: nail_style_recommend_tool
    group: nail
    use: deerflow.tools.nail.nail_style_recommend:nail_style_recommend_tool

  - name: user_pref_analytics_tool
    group: nail_ops
    use: deerflow.tools.nail.user_pref_analytics:user_pref_analytics_tool

  - name: nail_run_query_tool
    group: nail_dev
    use: deerflow.tools.nail.nail_run_query:nail_run_query_tool
```

- [ ] **Step 3: 重启后端验证工具注册**

```bash
cd /path/to/hackathon-meituan-ai/backend
uv run python -m uvicorn app.gateway.app:app --port 8001 --reload &
sleep 5
curl -s http://localhost:8001/api/nail/config/tools | python3 -c "
import json, sys
data = json.load(sys.stdin)
names = [t['name'] for t in data.get('nail_tools', [])]
assert 'nail_style_recommend_tool' in names, 'recommend tool missing'
assert 'user_pref_analytics_tool' in names, 'analytics tool missing'
assert 'nail_run_query_tool' in names, 'run query tool missing'
print('All 3 new tools registered OK')
"
```

期望输出：`All 3 new tools registered OK`

- [ ] **Step 4: 端到端测试 ops 页面 chat**

1. 访问 `http://localhost:3000/workspace/nail/dashboard`，用 ops 账号登录
2. 点击「🤖 AI 分析」
3. 在 chat 中输入：`分析本周热门美甲款式`
4. 确认 Agent 回复中调用了 `trend_query_tool` 或 `user_pref_analytics_tool`
5. 观察面板是否触发刷新

- [ ] **Step 5: 端到端测试 eval 页面 chat**

1. 访问 `http://localhost:3000/workspace/nail/evaluation`，用 dev 账号登录
2. 点击「🤖 AI 分析」
3. 输入：`分析最近一次 AI 试戴质量`
4. 确认 Agent 回复中调用了 `nail_run_query_tool` 并展示工具调用链数据

---

## 自检清单

- [ ] 所有新 Python 文件都有 `@tool` 装饰器且 docstring 描述参数和返回值
- [ ] `init_nail_tables()` 幂等，重复调用不报错
- [ ] `update_user_pref_vector` 失败时只 log，不抛异常
- [ ] nail_style_recommend_tool 在 ChromaDB 为空时降级返回 ops_signals 热门款式
- [ ] NailChatPane 在 SSE AbortError 时不显示错误信息
- [ ] NailPageLayout 在 chat 关闭时（isChatOpen=false）面板占满全宽
- [ ] ToolTimeline 在 toolChain 为空时显示"暂无工具调用记录"而不是崩溃
- [ ] config.yaml 3个新工具注册正确（`use:` 路径中模块名与文件名一致）
