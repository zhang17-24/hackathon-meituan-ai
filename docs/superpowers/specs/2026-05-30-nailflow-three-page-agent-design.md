# NailFlow 三端 ReAct Agent + RAG 推荐系统设计

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让运营看板和评分面板拥有与 AI 试戴相同的 DeerFlow ReAct chat 界面，同时重构 RAG 为真正的向量偏好推荐系统，并为每个页面配置独立的 Agent 提示词、工具集和对话历史。

**Architecture:** 单一 lead_agent + `nail_page_mode` config 注入控制三端行为差异；前端按页面隔离 thread_id；运营/评分页面采用「数据面板默认展示，点击 AI 分析后 chat 滑入」的 C 布局；RAG 重构为单一款式向量空间 + 用户偏好向量参数（加权滑动平均更新）。

**Tech Stack:** FastAPI + LangGraph (DeerFlow)、ChromaDB、SQLite、Next.js 16、React Query v5、ECharts、Tailwind CSS

---

## 一、整体架构

### 1.1 系统关系图

```
三个 NailFlow 页面
  /nail/tryon           /nail/dashboard         /nail/eval
  page_mode="tryon"     page_mode="ops"          page_mode="eval"
  thread: t-{userId}    thread: d-{userId}        thread: e-{userId}
  自定义上传UI           C布局: 面板 + Chat         C布局: 面板 + Chat
        │                      │                        │
        └──────────────────────┴────────────────────────┘
                               │ config.configurable.nail_page_mode
                               ▼
                  Lead Agent（单一实例）
                  ├── 读取 nail_page_mode
                  ├── 选择 system prompt prefix
                  ├── 过滤工具组（mode × nail_role × DB开关）
                  └── 返回 mode 对应欢迎语

              ┌──────────────┬──────────────┬──────────────┐
         [nail 工具组]  [nail_ops 工具组]  [nail_dev 工具组]
         试戴全链路      趋势/运营/方案     evaluation
         + recommend    + pref_analytics  + run_query

                               │
              ┌────────────────┼────────────────┐
        ChromaDB               SQLite            ChromaDB
        nail_styles         nail_user_prefs     (同左)
        (全款式库)           tool_call_log(新)
```

### 1.2 四个子系统构建顺序

```
① Per-page Chat 基础设施   ← 其他三个都依赖它（先做）
② RAG 推荐系统重构         ← 独立，可与①并行
③ 运营看板数据层            ← 依赖 ①②
④ 评分面板结构化数据层       ← 依赖 ①
```

### 1.3 新增数据结构汇总

| 类型 | 名称 | 用途 |
|------|------|------|
| SQLite 表 | `tool_call_log` | 每次 run 的工具调用链 + ReAct thinking |
| SQLite 表 | `nail_user_prefs` | 每用户一行偏好向量（JSON 浮点数组） |
| ChromaDB collection | `nail_styles` | 全款式静态向量库（含用户试戴图） |
| API | `GET /api/nail/config/page-mode/{mode}` | 返回欢迎语 + 建议问题 |
| API | `POST /api/nail/styles/{style_id}/save` | 收藏款式（写偏好 + ops_signal） |
| 工具 | `nail_style_recommend_tool` | 基于 pref_vec 最近邻推荐 |
| 工具 | `user_pref_analytics_tool` | 聚合全体用户偏好分布 |
| 工具 | `nail_run_query_tool` | 查询试戴完整执行数据 |

---

## 二、Per-page ReAct Chat 基础设施

### 2.1 后端：nail_page_mode 注入

**文件：** `backend/packages/harness/deerflow/agents/lead_agent/agent.py`

在已有 `nail_role` 提取逻辑之后，增加 `nail_page_mode` 读取：

```python
nail_page_mode = cfg.get("nail_page_mode", "tryon")  # "tryon"|"ops"|"eval"

_MODE_TOOL_GROUPS = {
    "tryon": ["nail"],
    "ops":   ["nail", "nail_ops"],
    "eval":  ["nail", "nail_ops", "nail_dev"],
}

# 叠加 nail_role 权限过滤（取交集：mode要求的组 ∩ role有权访问的组）
allowed_by_role = _ROLE_GROUPS.get(nail_role, ["nail"])
mode_groups = _MODE_TOOL_GROUPS.get(nail_page_mode, ["nail"])
nail_groups = [g for g in mode_groups if g in allowed_by_role]

# 叠加 DB 工具开关
tools = get_available_tools(
    groups=nail_groups,
    page_mode=nail_page_mode,      # 新增：工具管理里的页面开关
)
```

**文件：** `backend/packages/harness/deerflow/agents/lead_agent/prompt.py`

新增 mode → prompt prefix 映射：
```python
_MODE_PROMPT_PREFIX = {
    "tryon": """你是 NailFlow AI 美甲试戴助手...""",
    "ops":   """你是 NailFlow 运营分析助手，专注于...""",
    "eval":  """你是 NailFlow 评分分析助手，负责...""",
}
```

### 2.2 工具管理页面扩展

**文件：** `backend/app/gateway/routers/nail_config.py`

`nail_tool_overrides` 表新增 `enabled_pages` 字段（JSON 数组，如 `["tryon","ops"]`）。

`PUT /api/nail/config/tools/{name}` 接受 `enabled_pages` 参数。

**文件：** `frontend/src/components/nail/tool-card.tsx`

每个 ToolCard 在开关下方增加「页面启用」行：

```tsx
<div className="flex gap-2 mt-2">
  {["tryon","ops","eval"].map(mode => (
    <label key={mode} className="flex items-center gap-1 text-xs">
      <input type="checkbox"
        checked={tool.enabled_pages?.includes(mode)}
        onChange={() => togglePage(tool.name, mode)}
      />
      {MODE_LABELS[mode]}
    </label>
  ))}
</div>
```

### 2.3 新增页面欢迎语 API

**文件：** `backend/app/gateway/routers/nail_config.py` 新增端点：

```python
@router.get("/page-mode/{mode}")
async def get_page_mode_config(mode: str):
    configs = {
        "tryon": {
            "title": "AI 美甲试戴助手",
            "subtitle": "上传手图和款式图，我来帮你完成试戴",
            "suggestions": ["帮我试戴这款法式美甲", "推荐适合我的款式", "分析这个款式的特点"]
        },
        "ops": {
            "title": "运营分析助手",
            "subtitle": "分析趋势数据，生成运营方案",
            "suggestions": ["分析本周热门款式", "生成营销方案", "查看用户偏好分布"]
        },
        "eval": {
            "title": "评分分析助手",
            "subtitle": "评估试戴质量，生成答辩证据",
            "suggestions": ["分析最近一次试戴", "哪里扣分最多？", "生成答辩证据清单"]
        },
    }
    return configs.get(mode, configs["tryon"])
```

### 2.4 前端：per-page thread 隔离

**新文件：** `frontend/src/core/nail-chat/use-nail-thread.ts`

```typescript
export function useNailThread(pageMode: "tryon" | "ops" | "eval") {
  const { user } = useAuth();
  const userId = (user as any)?.id ?? "anon";
  const key = `nail_thread_${pageMode}_${userId}`;

  const [threadId, setThreadId] = useState<string>(() =>
    localStorage.getItem(key) ?? ""
  );

  const ensureThread = useCallback(async () => {
    if (threadId) return threadId;
    const res = await fetch("/api/v1/threads", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).then(r => r.json());
    const id = res.thread_id ?? res.id;
    localStorage.setItem(key, id);
    setThreadId(id);
    return id;
  }, [threadId, key]);

  const resetThread = useCallback(() => {
    localStorage.removeItem(key);
    setThreadId("");
  }, [key]);

  return { threadId, ensureThread, resetThread };
}
```

### 2.5 前端：C 布局通用组件

**新文件：** `frontend/src/components/nail/nail-page-layout.tsx`

```tsx
interface NailPageLayoutProps {
  pageMode: "ops" | "eval";
  panel: React.ReactNode;       // 左侧数据面板
  chatConfig?: Record<string, any>;  // 额外 configurable 参数
}

export function NailPageLayout({ pageMode, panel, chatConfig }: NailPageLayoutProps) {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { threadId, ensureThread } = useNailThread(pageMode);
  const { data: modeConfig } = usePageModeConfig(pageMode);

  return (
    <div className="flex h-full flex-col">
      <Header>
        <Button onClick={() => setIsChatOpen(v => !v)}>
          🤖 AI 分析 {isChatOpen ? "←" : "→"}
        </Button>
      </Header>
      <div className="flex flex-1 min-h-0">
        {/* 左侧数据面板 */}
        <div className={cn("flex-1 overflow-auto p-4 transition-all",
          isChatOpen ? "w-[60%]" : "w-full")}>
          {panel}
        </div>
        {/* 右侧 Chat（滑入动画） */}
        {isChatOpen && (
          <div className="w-[40%] border-l flex flex-col">
            <NailChatPane
              threadId={threadId}
              pageMode={pageMode}
              modeConfig={modeConfig}
              extraConfig={chatConfig}
              onEnsureThread={ensureThread}
            />
          </div>
        )}
      </div>
    </div>
  );
}
```

**新文件：** `frontend/src/components/nail/nail-chat-pane.tsx`

内嵌 DeerFlow 的 `MessageList` + `InputBox`，传入 `nail_page_mode` 到 run 请求的 `config.configurable`。

---

## 三、RAG 推荐系统重构

### 3.1 数据结构

**ChromaDB collection: `nail_styles`**（唯一一个，全款式库）

```
document:  款式文字描述（LLM 自动生成或人工标注）
embedding: 描述文字的嵌入向量
metadata:
  style_id:    "french-001"
  category:    "法式 | 渐变 | 纯色 | 花纹 | 艺术"
  color_tags:  "white,pink,gold"
  source:      "static" | "user_tryon"
  image_path:  "美甲图片/款式图/french-001.jpg"
id: style_id（静态）或 "tryon_{run_id}"（用户试戴图）
```

**SQLite 表: `nail_user_prefs`**

```sql
CREATE TABLE IF NOT EXISTS nail_user_prefs (
    user_id    TEXT PRIMARY KEY,
    pref_vector TEXT NOT NULL,   -- JSON 序列化浮点数组（与 ChromaDB 嵌入同维度）
    trial_count INTEGER DEFAULT 0,
    save_count  INTEGER DEFAULT 0,
    updated_at  TEXT
);
```

### 3.2 偏好向量更新算法

**文件：** `backend/packages/harness/deerflow/tools/nail/preference_rag.py`（重构）

```python
SIGNAL_WEIGHT = {"tryon": 1.0, "save": 3.0, "search": 2.0}
HISTORY_DECAY = 0.8   # 历史偏好保留比例
NEW_SIGNAL_RATIO = 0.2  # 新信号影响比例

def update_user_pref_vector(user_id: str, style_id: str, signal_type: str):
    """获取款式向量，与用户历史偏好加权融合，更新 nail_user_prefs。"""
    col = _get_collection()

    # 1. 获取款式在向量空间的位置
    result = col.get(ids=[style_id], include=["embeddings"])
    if not result["embeddings"]:
        return  # 款式不在库中，跳过
    style_vec = np.array(result["embeddings"][0])

    # 2. 获取用户历史偏好向量
    with get_db() as conn:
        row = conn.execute(
            "SELECT pref_vector FROM nail_user_prefs WHERE user_id=?", (user_id,)
        ).fetchone()

    if row is None:
        # 首次：直接用款式向量作为初始偏好
        new_pref = style_vec
    else:
        old_pref = np.array(json.loads(row[0]))
        weight = SIGNAL_WEIGHT.get(signal_type, 1.0)
        # 加权滑动平均
        new_pref = old_pref * HISTORY_DECAY + style_vec * NEW_SIGNAL_RATIO * weight
        # 归一化，保持向量模长稳定
        norm = np.linalg.norm(new_pref)
        if norm > 0:
            new_pref = new_pref / norm

    # 3. 更新到 DB
    with get_db() as conn:
        conn.execute("""
            INSERT INTO nail_user_prefs (user_id, pref_vector, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                pref_vector = excluded.pref_vector,
                updated_at  = excluded.updated_at
        """, (user_id, json.dumps(new_pref.tolist())))
```

### 3.3 推荐工具：`nail_style_recommend_tool`

**文件：** `backend/packages/harness/deerflow/tools/nail/nail_style_recommend.py`（新建）

```python
@tool
def nail_style_recommend_tool(user_id: str, top_k: int = 5) -> str:
    """基于用户偏好向量，推荐向量空间中最近邻的美甲款式。

    Args:
        user_id: 用户 ID
        top_k: 返回推荐数量，默认 5

    Returns:
        {"recommendations": [...], "count": n, "message": "..."}
    """
    try:
        # 1. 获取用户偏好向量
        with get_db() as conn:
            row = conn.execute(
                "SELECT pref_vector FROM nail_user_prefs WHERE user_id=?", (user_id,)
            ).fetchone()

        col = _get_collection()

        if row is None:
            # 冷启动：返回热门款式（ops_signals 点击量最高）
            return _cold_start_recommend(top_k)

        pref_vec = json.loads(row[0])

        # 2. 用偏好向量直接查最近邻
        results = col.query(
            query_embeddings=[pref_vec],
            n_results=top_k + 10,  # 多取一些，过滤后返回 top_k
            include=["documents", "metadatas", "distances"],
        )
        docs   = results["documents"][0]
        metas  = results["metadatas"][0]
        dists  = results["distances"][0]

        # 3. 过滤已试戴款式
        tried = _get_tried_styles(user_id)
        recs = [
            {
                "style_id":    m.get("style_id"),
                "description": doc,
                "category":    m.get("category"),
                "image_path":  m.get("image_path"),
                "similarity":  round(1 - d, 3),
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
        return json.dumps({"recommendations": [], "count": 0, "error": str(e)})
```

### 3.4 冷启动脚本

**新文件：** `backend/scripts/init_nail_styles.py`

```
1. 扫描 data/mock/nail_styles/ 和 美甲图片/款式图/ 目录
2. 对每张图片：调用 LLM 生成中文款式描述（颜色/甲型/风格/材质）
3. 批量写入 ChromaDB nail_styles collection
4. 写入 SQLite nail_catalog 表（style_id + image_path + description）
```

### 3.5 收藏 API

**文件：** `backend/app/gateway/routers/nail_ops.py` 新增端点：

```python
@router.post("/api/nail/styles/{style_id}/save")
@require_auth
async def save_style(style_id: str, request: Request):
    user = request.state.user
    # 1. 更新用户偏好向量（强信号 weight=3.0）
    update_user_pref_vector(user.id, style_id, "save")
    # 2. 写入 ops_signals（为运营看板提供数据）
    with get_db() as conn:
        conn.execute(
            "INSERT INTO ops_signals (style_id, signal_type, ...) VALUES (?,?,?)",
            (style_id, "save", ...)
        )
    return {"saved": True}
```

---

## 四、运营看板数据层

### 4.1 页面布局

C 方案：数据面板默认展示，点击「🤖 AI 分析」后 chat 从右侧滑入（占 40% 宽度）。

### 4.2 数据面板 4 个模块

| 模块 | 数据来源 | API |
|------|---------|-----|
| **款式热度榜** | `ops_signals` GROUP BY style_id | `GET /api/nail/dashboard?days=7`（已有，扩展返回 top_styles） |
| **趋势折线图** | `ops_signals` GROUP BY date | 同上，扩展 `trend_series` 字段 |
| **用户偏好风格分布** | `nail_user_prefs` K-means 聚类 | `GET /api/nail/analytics/pref-distribution` 新增 |
| **ActionProposal 列表** | `action_proposals` | `GET /api/nail/proposals`（已有） |

图表渲染：ECharts（项目已有）。Agent 调用工具后工具返回 `"refresh_signals": true`，前端监听派发 `CustomEvent("nail:refresh-dashboard")` 触发面板刷新。

### 4.3 ops Agent 工具集

默认工具（ops mode）：
- 已有：`trend_query_tool`, `trend_discovery_tool`, `ops_analysis_tool`, `action_proposal_tool`, `customer_service_tool`
- 新增：`nail_style_recommend_tool`（查看某用户推荐）
- 新增：`user_pref_analytics_tool`（全体用户偏好聚合）

**新文件：** `backend/packages/harness/deerflow/tools/nail/user_pref_analytics.py`

```python
@tool
def user_pref_analytics_tool(top_k_clusters: int = 5) -> str:
    """聚合分析全体用户偏好分布，识别主要风格群体。

    Returns:
        {"clusters": [...], "total_users": n, "top_styles": [...]}
    """
    # 1. 读取所有 nail_user_prefs
    # 2. K-means 聚类（k=top_k_clusters）
    # 3. 每个聚类找最近邻款式作为"代表款"
    # 4. 返回聚类大小 + 代表款 + 用户占比
```

### 4.4 前端改造

**文件：** `frontend/src/app/workspace/nail/dashboard/page.tsx`

- 保留现有静态面板（signals + proposals）
- 增加「趋势折线图」和「偏好风格分布饼图」两个 ECharts 组件
- 使用 `NailPageLayout` 组件包装，传入 `pageMode="ops"`
- 新增 `useEffect` 监听 `nail:refresh-dashboard` 事件触发重新拉取数据

---

## 五、评分面板 Chat + 结构化数据层

### 5.1 页面布局

C 方案：评分面板默认展示，点击「🤖 AI 分析」后 chat 从右侧滑入。

### 5.2 新增：tool_call_log 表

```sql
CREATE TABLE IF NOT EXISTS tool_call_log (
    id          TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL,
    tool_name   TEXT NOT NULL,
    call_index  INTEGER,
    input_json  TEXT,
    output_json TEXT,
    thinking    TEXT,          -- Agent ReAct Thought 文字
    duration_ms INTEGER,
    created_at  TEXT,
    FOREIGN KEY (run_id) REFERENCES nail_runs(id)
);
```

**写入时机：** 在 lead_agent 中间件层拦截每次工具调用事件（SSE `tool_call` + `tool_result` 事件对），自动写入，对工具代码零侵入。

**写入位置：** `backend/packages/harness/deerflow/agents/lead_agent/agent.py` 的工具调用拦截点：

```python
# 在工具执行 wrapper 中记录
async def tool_call_middleware(tool_name, input_data, call_fn):
    start = time.time()
    try:
        result = await call_fn(input_data)
        duration = int((time.time() - start) * 1000)
        _log_tool_call(run_id, tool_name, input_data, result, thinking, duration)
        return result
    except Exception as e:
        _log_tool_call(run_id, tool_name, input_data, None, thinking, -1, error=str(e))
        raise
```

### 5.3 新增工具：nail_run_query_tool

**新文件：** `backend/packages/harness/deerflow/tools/nail/nail_run_query.py`

```python
@tool
def nail_run_query_tool(user_id: str = "", limit: int = 3) -> str:
    """查询最近 N 次试戴的完整执行数据，包含工具调用链和 Agent 思考过程。

    Args:
        user_id: 过滤指定用户（空则返回最近全局记录）
        limit: 返回条数，默认 3

    Returns:
        {
            "runs": [
                {
                    "run_id": "xxx",
                    "total_duration_ms": 18420,
                    "tool_chain": [
                        {"tool": "hand_detect_tool", "duration_ms": 320, "success": true},
                        ...
                    ],
                    "thinking_log": ["检测到手部...", ...],
                    "final_result": {"result_path": "...", "quality_scores": {...}}
                }
            ]
        }
    """
```

### 5.4 评分面板新增：工具调用时序图

**新文件：** `frontend/src/components/nail/tool-timeline.tsx`

纯 CSS 实现甘特图风格时序图：

```
hand_detect  ████ 320ms  ✓
nail_mask    ███ 280ms   ✓
style_under  ████████ 850ms  ✓
prompt_build ████ 410ms  ✓
image_gen    ████████████████ 14200ms  ✓
quality_chk  ████ 360ms  ✓
──────────────────────────────
总计: 18.4s   全部成功 ✓ / 1 失败 ✗
```

### 5.5 前端改造

**文件：** `frontend/src/app/workspace/nail/evaluation/page.tsx`

- 保留现有评分圆环 + rubric 条形图 + 问题/任务列表
- 新增「工具调用时序图」组件（ToolTimeline）
- 使用 `NailPageLayout` 组件包装，传入 `pageMode="eval"`
- eval Agent 工具集：`evaluation_tool` + `nail_run_query_tool` + `trend_query_tool`

---

## 六、文件改动清单

### 后端新建文件

| 文件 | 说明 |
|------|------|
| `tools/nail/nail_style_recommend.py` | 偏好向量推荐工具 |
| `tools/nail/user_pref_analytics.py` | 全体用户偏好聚合工具 |
| `tools/nail/nail_run_query.py` | 试戴执行数据查询工具 |
| `scripts/init_nail_styles.py` | ChromaDB 款式库冷启动脚本 |

### 后端修改文件

| 文件 | 改动 |
|------|------|
| `tools/nail/base.py` | 新增 `tool_call_log`, `nail_user_prefs` 表；新增 `update_user_pref_vector()` |
| `tools/nail/preference_rag.py` | 重构为偏好向量更新逻辑 |
| `agents/lead_agent/agent.py` | 新增 `nail_page_mode` 注入 + 工具调用拦截中间件 |
| `agents/lead_agent/prompt.py` | 新增 `_MODE_PROMPT_PREFIX` 映射 |
| `routers/nail_config.py` | 新增 `GET /api/nail/config/page-mode/{mode}` + tools `enabled_pages` 支持 |
| `routers/nail_ops.py` | 新增 `POST /api/nail/styles/{style_id}/save`；扩展 dashboard API |
| `routers/models.py` | 新增 `GET /api/nail/analytics/pref-distribution` |
| `app.py` lifespan | 新增 `init_nail_styles` 冷启动（可选，按需） |
| `config.yaml` | 注册 3 个新工具 |

### 前端新建文件

| 文件 | 说明 |
|------|------|
| `core/nail-chat/use-nail-thread.ts` | per-page thread 隔离 hook |
| `components/nail/nail-page-layout.tsx` | C 布局通用容器 |
| `components/nail/nail-chat-pane.tsx` | 内嵌 DeerFlow chat |
| `components/nail/tool-timeline.tsx` | 工具调用时序图组件 |

### 前端修改文件

| 文件 | 改动 |
|------|------|
| `app/workspace/nail/dashboard/page.tsx` | 使用 NailPageLayout + 新增 ECharts 图表 |
| `app/workspace/nail/evaluation/page.tsx` | 使用 NailPageLayout + 新增 ToolTimeline |
| `components/nail/tool-card.tsx` | 新增「页面启用」开关行 |

---

## 七、实现约束

- **功能降级**：ChromaDB 初始化失败时，`nail_style_recommend_tool` 降级为返回热门款式（从 ops_signals 取 top-5）
- **向量维度**：必须与 ChromaDB `nail_styles` collection 使用的嵌入函数保持一致（均用 ChromaDB 默认的 `all-MiniLM-L6-v2`）
- **工具调用拦截**：tool_call_log 写入失败不能影响正常工具执行，必须在 `try/except` 包裹内
- **thread 隔离**：localStorage key 包含 userId，不同用户登录同一浏览器时不会串 thread

---

*设计日期：2026-05-30*
