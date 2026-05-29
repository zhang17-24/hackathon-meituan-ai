# NailFlow 工具管理 + 模型配置 + Agent 模型选择 设计文档

> 状态：设计已确认，待进入实现计划阶段
> 日期：2026-05-29

---

## 一、背景与目标

当前 NailFlow 存在三个痛点：

1. **模型只能在 config.yaml 里配置**：用户必须修改代码文件并重启服务，体验差
2. **没有工具管理页面**：13 个 nail 工具 + DeerFlow 内置工具无处可视化管理，无法开关
3. **无法为不同 Agent/工具指定模型**：主 Agent、视觉工具、运营工具都用同一个模型，无法优化成本和效果

**目标**：通过三个相互配合的子系统，让用户在 UI 上完成所有模型和工具的配置，无需修改代码。

---

## 二、整体架构

### 2.1 三层职责分离（方案 C）

```
Settings「模型配置」tab     ← 模型 CRUD（增删改查）+ 全局 Agent 默认模型绑定
         ↓
工具管理页 /workspace/tools  ← 工具开关 + 每个 LLM 工具的模型覆盖
         ↓
对话页顶部快速选择器          ← 当前会话的主 Agent 模型临时覆盖（localStorage）
```

### 2.2 数据存储（混合方案）

- **config.yaml**（静态）：手动配置的模型，只读，优先级低
- **SQLite DB**（动态）：用户通过 UI 创建的模型，可 CRUD，优先级高
- **运行时合并**：`GET /api/models` 将两者合并后返回，DB 模型优先

### 2.3 数据流

```
用户在 Settings 创建模型
  → 写入 nail_model_configs 表
  → GET /api/models 合并返回（DB + config.yaml）
  → 对话页下拉 / 工具卡片下拉 读取模型列表

用户在 Settings 绑定 Agent 默认模型
  → 写入 nail_agent_configs 表
  → 后端 lead_agent.py 启动时读取

用户在工具页覆盖单工具模型
  → 写入 nail_tool_overrides 表
  → 对应工具调用 create_chat_model() 时读取

用户在对话页顶部选择器临时切换模型
  → 写入 localStorage: deerflow.thread-model.{threadId}
  → SSE 请求 config.configurable.model_name 透传给后端
```

---

## 三、新增数据库表（3 张）

### 3.1 nail_model_configs — 用户创建的模型

```sql
CREATE TABLE IF NOT EXISTS nail_model_configs (
  id           TEXT PRIMARY KEY,
  name         TEXT UNIQUE NOT NULL,      -- 唯一标识，如 "qwen-max"
  display_name TEXT NOT NULL,
  provider     TEXT NOT NULL,             -- "qwen"|"deepseek"|"doubao"|"kimi"|"custom"
  model_id     TEXT NOT NULL,             -- 提供商模型名，如 "qwen-max"
  api_key      TEXT,                      -- 存储（暂明文，后续可加密）
  api_base     TEXT NOT NULL,
  use_class    TEXT NOT NULL,             -- Python 类路径
  supports_vision  BOOL DEFAULT 0,
  supports_thinking BOOL DEFAULT 0,
  is_active    BOOL DEFAULT 1,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 nail_agent_configs — Agent 全局模型绑定

```sql
CREATE TABLE IF NOT EXISTS nail_agent_configs (
  config_key   TEXT PRIMARY KEY,  -- "main_agent" | "tool_default"
  model_name   TEXT NOT NULL,     -- 指向 nail_model_configs.name 或 config.yaml 模型名
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3.3 nail_tool_overrides — 工具级模型覆盖与开关

```sql
CREATE TABLE IF NOT EXISTS nail_tool_overrides (
  tool_name    TEXT PRIMARY KEY,  -- 工具函数名，如 "style_understanding_tool"
  model_name   TEXT,              -- NULL 表示跟随 tool_default
  is_enabled   BOOL DEFAULT 1,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 四、新增后端 API

### 4.1 模型 CRUD

```
GET    /api/nail/config/models             → 用户自定义模型列表
POST   /api/nail/config/models             → 创建模型
PUT    /api/nail/config/models/{name}      → 更新模型
DELETE /api/nail/config/models/{name}      → 删除模型
POST   /api/nail/config/models/test        → 测试模型连接
```

### 4.2 Agent 绑定

```
GET  /api/nail/config/agents               → 获取 main_agent + tool_default 绑定
PUT  /api/nail/config/agents               → 更新绑定
```

### 4.3 工具管理

```
GET  /api/nail/config/tools                → 工具列表（含开关 + 模型覆盖）
PUT  /api/nail/config/tools/{tool_name}    → 更新工具开关 / 模型覆盖
```

### 4.4 GET /api/models 增强（合并逻辑）

修改 `backend/app/gateway/routers/models.py`：
1. 先读 `nail_model_configs`（DB，活跃状态）
2. 再读 `config.yaml` 的 `models` 列表
3. 按 `name` 去重，DB 模型优先
4. 合并返回

---

## 五、子系统一：Settings「模型配置」Tab

### 5.1 入口

在 `settings-dialog.tsx` 的 tab 列表中插入第 2 个 tab（account 后）：

```
account → 模型配置(new) → appearance → memory → tools → skills → notification → about
```

`defaultSection` 参数支持 `"models"` 值，供外部直接打开。

### 5.2 页面布局

**上半区：已配置模型列表**
- 展示 DB 中的用户模型（可编辑/删除/切换启用状态）
- 展示 config.yaml 的静态模型（只读，带"静态"标签）
- 右上角「+ 添加模型」按钮

**下半区：Agent 默认模型绑定**
- 主 Agent（NailPlannerAgent）：下拉选择模型
- 工具默认模型（所有 LLM 工具的兜底）：下拉选择模型

### 5.3 添加/编辑模型表单（Dialog）

**步骤 1：选择提供商**
```
[千问(Qwen)] [DeepSeek] [豆包(Doubao)] [Kimi] [自定义]
```

**步骤 2：填写配置（选择提供商后自动填入 api_base 和 use_class）**
- 名称（唯一 ID，可改）
- 显示名称（可改）
- 模型 ID（下拉预设列表 + 支持手动输入）
- API Base URL（预填，可改）
- API Key（密文输入框）
- 支持视觉 / 支持思考（复选框）

**底部操作**：[取消] [测试连接] [保存]

### 5.4 四大提供商预设

| 提供商 | use_class | api_base | 预设模型 |
|--------|-----------|----------|----------|
| **千问** | `langchain_openai:ChatOpenAI` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | qwen-max, qwen-plus, qwen-turbo, qwen-vl-max(视觉) |
| **DeepSeek** | `langchain_openai:ChatOpenAI` | `https://api.deepseek.com/v1` | deepseek-chat, deepseek-reasoner(思考) |
| **豆包** | `deerflow.models.patched_deepseek:PatchedChatDeepSeek` | `https://ark.cn-beijing.volces.com/api/v3` | doubao-seed-1.8(视觉+思考), doubao-pro-32k |
| **Kimi** | `langchain_openai:ChatOpenAI` | `https://api.moonshot.cn/v1` | moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k |
| **自定义** | 手动输入 | 手动输入 | 手动输入 |

### 5.5 前端文件变更

```
frontend/src/components/workspace/settings/
  ├── settings-dialog.tsx            ← 插入 "models" tab
  ├── model-settings-page.tsx        ← 新建：模型列表 + Agent 绑定
  └── model-form-dialog.tsx          ← 新建：添加/编辑表单

frontend/src/core/nail-models/       ← 新建目录
  ├── api.ts                         ← CRUD 接口调用
  ├── hooks.ts                       ← useNailModels / useAgentConfigs
  └── types.ts                       ← NailModelConfig / AgentConfig
```

---

## 六、子系统二：工具管理页

### 6.1 入口

侧边栏 NailFlow 区块新增导航项：

```
NailFlow
  💅 AI 试戴
  📊 运营看板
  ⚡ 评分面板
  🔧 工具           ← 新增，nail_role 所有角色可见
```

路由：`/workspace/nail/tools`

### 6.2 页面布局

```
header: NailFlow › 工具管理                    [搜索工具输入框]

┌─ NailFlow 工具（13个）──────────────────────────────────────┐
│  按组显示：nail（8个）/ nail_ops（4个）/ nail_dev（1个）       │
│  每个工具一张卡片（见 6.3）                                    │
└───────────────────────────────────────────────────────────── ┘

┌─ DeerFlow 内置工具 ─────────────────────────────────────────┐
│  按组显示：web / file / bash 等                               │
│  每个工具一张卡片（简化版，无模型选择）                          │
└───────────────────────────────────────────────────────────── ┘
```

### 6.3 工具卡片设计

**无 LLM 的工具**：
```
┌──────────────────────────────────────────────────────────┐
│ {emoji} {display_name}  {tool_name}  [{group}]  ●──○ 开关│
│ {description}                                             │
└──────────────────────────────────────────────────────────┘
```

**需要 LLM 的工具**（增加模型绑定行）：
```
┌──────────────────────────────────────────────────────────┐
│ {emoji} {display_name}  {tool_name}  [{group}]  ●──○ 开关│
│ {description}                                             │
│ 模型绑定：[工具默认 (DeepSeek-Chat) ▼]                    │
│           ⚠️ 此工具需要视觉能力，建议选支持视觉的模型        │  ← 仅 requires_vision=true 时显示
└──────────────────────────────────────────────────────────┘
```

**模型下拉内容**：
- 第一项：「工具默认（{tool_default 模型名}）」
- 然后列出所有可用模型，requires_vision=true 时过滤不支持视觉的模型（显示灰色警告）

### 6.4 需要 LLM 的工具清单

| 工具 | 是否需要视觉 |
|------|------------|
| `style_understanding_tool` | ✅ 需要 |
| `quality_check_tool` | ✅ 需要 |
| `ops_analysis_tool` | ❌ |
| `customer_service_tool` | ❌ |
| `trend_discovery_tool` | ❌ |
| `evaluation_tool` | ❌ |

### 6.5 GET /api/nail/config/tools 响应格式

```json
{
  "nail_tools": [
    {
      "name": "hand_detect_tool",
      "display_name": "手部检测",
      "emoji": "🔍",
      "description": "用 MediaPipe 识别手指位置和甲床 bbox，无需 API Key",
      "group": "nail",
      "requires_llm": false,
      "requires_vision": false,
      "is_enabled": true,
      "model_override": null
    },
    {
      "name": "style_understanding_tool",
      "display_name": "款式理解",
      "emoji": "🎨",
      "description": "调用 LLM Vision 解析款式颜色/纹理/甲型/饰品，输出 style_tags",
      "group": "nail",
      "requires_llm": true,
      "requires_vision": true,
      "is_enabled": true,
      "model_override": null
    }
  ],
  "builtin_tools": [
    {
      "name": "web_search",
      "display_name": "网页搜索",
      "emoji": "🌐",
      "description": "DuckDuckGo 网页搜索，无需 API Key",
      "group": "web",
      "requires_llm": false,
      "is_enabled": true
    }
  ]
}
```

### 6.6 前端文件变更

```
frontend/src/app/workspace/nail/tools/
  └── page.tsx                         ← 新建：工具管理主页面

frontend/src/components/nail/
  ├── tool-card.tsx                    ← 新建：工具卡片
  └── model-selector-inline.tsx       ← 新建：卡片内嵌模型选择器

frontend/src/components/workspace/nail-nav.tsx  ← 添加 🔧 工具 导航项
```

---

## 七、子系统三：对话页模型快速选择器

### 7.1 位置

对话页右上角 header，紧挨 Tokens 按钮左侧：

```
对话页顶部：  [🤖 Qwen-Max ▼]  [Tokens — ▼]
```

### 7.2 下拉内容

```
✓ Qwen-Max          千问   视觉✓
  DeepSeek-Chat      DeepSeek
  Doubao-Seed-1.8    豆包  视觉✓ 思考✓
  ──────────────────────────────────
  来自 config.yaml：
  doubao-seed-1.8（静态）
  ──────────────────────────────────
  🔗 去设置页配置更多模型
```

### 7.3 存储与传递

- **存储**：`localStorage: deerflow.thread-model.{threadId}`（复用 DeerFlow 现有机制）
- **传递**：SSE 请求 `config.configurable.model_name` 透传给后端
- **默认值**：读 `nail_agent_configs.main_agent`；若无则用第一个可用模型

### 7.4 前端文件变更

```
frontend/src/components/nail/
  └── nail-model-picker.tsx            ← 新建：对话页顶部模型选择器

frontend/src/app/workspace/chats/[thread_id]/page.tsx  ← 在 header 区插入组件
```

---

## 八、后端模型优先级链

```
对话请求传入的 model_name（会话级，localStorage）
  → nail_agent_configs["main_agent"]（Settings 全局主 Agent 默认）
    → config.yaml 第一个模型（DeerFlow 原有行为）

工具调用 create_chat_model() 时：
  → nail_tool_overrides[tool_name].model_name（工具页覆盖）
    → nail_agent_configs["tool_default"]（Settings 全局工具默认）
      → 主 Agent 同款模型（兜底）
```

### 8.1 后端修改点

```python
# 1. backend/packages/harness/deerflow/tools/nail/base.py
#    init_nail_tables() 添加三张新表

# 2. backend/app/gateway/routers/nail_config.py  ← 新建
#    实现 /api/nail/config/models、/agents、/tools 端点

# 3. backend/app/gateway/app.py
#    include_router(nail_config_router)

# 4. backend/app/gateway/routers/models.py
#    GET /api/models 合并 DB + config.yaml

# 5. backend/packages/harness/deerflow/agents/lead_agent/agent.py
#    _make_lead_agent() 读 nail_agent_configs["main_agent"] 覆盖 model_name

# 6. backend/packages/harness/deerflow/tools/nail/{style_understanding,quality_check,...}.py
#    create_chat_model() 调用前读 nail_tool_overrides 获取 model_name
```

---

## 九、文件变更全览

### 后端新增/修改

```
backend/packages/harness/deerflow/tools/nail/base.py     ← 添加3张新表到 init_nail_tables()
backend/app/gateway/routers/nail_config.py               ← 新建：模型/Agent/工具 CRUD API
backend/app/gateway/routers/models.py                    ← 修改：合并 DB + config.yaml
backend/app/gateway/app.py                               ← 注册 nail_config_router
backend/packages/harness/deerflow/agents/lead_agent/agent.py  ← 读 nail_agent_configs
backend/packages/harness/deerflow/tools/nail/style_understanding.py  ← 读 nail_tool_overrides
backend/packages/harness/deerflow/tools/nail/quality_check.py        ← 同上
backend/packages/harness/deerflow/tools/nail/ops_analysis.py         ← 同上
backend/packages/harness/deerflow/tools/nail/customer_service.py     ← 同上
backend/packages/harness/deerflow/tools/nail/trend_discovery.py      ← 同上
backend/packages/harness/deerflow/tools/nail/evaluation.py           ← 同上
```

### 前端新增/修改

```
frontend/src/core/nail-models/
  ├── api.ts            ← 新建
  ├── hooks.ts          ← 新建
  └── types.ts          ← 新建

frontend/src/components/workspace/settings/
  ├── settings-dialog.tsx          ← 修改：插入 "models" tab
  ├── model-settings-page.tsx      ← 新建
  └── model-form-dialog.tsx        ← 新建

frontend/src/components/nail/
  ├── nail-model-picker.tsx        ← 新建
  ├── tool-card.tsx                ← 新建
  └── model-selector-inline.tsx   ← 新建

frontend/src/app/workspace/nail/tools/page.tsx  ← 新建
frontend/src/app/workspace/chats/[thread_id]/page.tsx  ← 修改：插入 NailModelPicker
frontend/src/components/workspace/nail-nav.tsx         ← 修改：添加 🔧 工具 导航项
```

---

## 十、开发优先级

按依赖关系，建议开发顺序：

1. **DB 表 + `/api/nail/config/*` API**（后端基础，三个子系统共用）
2. **GET /api/models 合并逻辑**（让前端能读到所有可用模型）
3. **Settings「模型配置」Tab**（用户可创建模型，解锁 AI 功能）
4. **工具管理页**（工具开关 + 模型绑定）
5. **对话页模型选择器**（会话级快速切换）
6. **后端 Agent/工具读取配置**（让绑定生效）

---

*文档持续更新，每次设计对话后同步追加*
