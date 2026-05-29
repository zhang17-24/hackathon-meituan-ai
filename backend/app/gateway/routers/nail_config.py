# backend/app/gateway/routers/nail_config.py
"""NailFlow 配置 API：模型 CRUD、Agent 绑定、工具开关管理。"""
import json
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


def _safe_parse_pages(raw: str | None) -> list[str]:
    """安全解析 enabled_pages JSON，失败时返回默认值。"""
    if not raw:
        return ["tryon", "ops", "eval"]
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else ["tryon", "ops", "eval"]
    except Exception:
        return ["tryon", "ops", "eval"]


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
    source: str = "db"


class AgentConfigUpdate(BaseModel):
    main_agent: Optional[str] = None
    tool_default: Optional[str] = None


class ToolOverrideUpdate(BaseModel):
    model_name: Optional[str] = None
    is_enabled: Optional[bool] = None
    enabled_pages: Optional[list[str]] = None  # ["tryon","ops","eval"] 的子集


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
        created_at=r["created_at"], source="db",
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
             int(body.supports_vision), int(body.supports_thinking), now, now),
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
                "VALUES ('main_agent', ?, ?)",
                (body.main_agent, now),
            )
        if body.tool_default is not None:
            conn.execute(
                "INSERT OR REPLACE INTO nail_agent_configs (config_key, model_name, updated_at) "
                "VALUES ('tool_default', ?, ?)",
                (body.tool_default, now),
            )
        conn.commit()
    return {"message": "更新成功"}


# ─── 工具管理 ─────────────────────────────────────────────

_NAIL_TOOL_META = [
    ("hand_detect_tool",         "手部检测",   "🔍", "用 MediaPipe 识别手指位置和甲床 bbox，无需 API Key",              "nail",     False, False),
    ("nail_mask_tool",           "甲面遮罩",   "✂️", "根据 bbox 生成甲面 mask PNG，白色=甲面，黑色=其他",              "nail",     False, False),
    ("style_understanding_tool", "款式理解",   "🎨", "调用 LLM Vision 解析款式颜色/纹理/甲型/饰品，输出 style_tags",   "nail",     True,  True),
    ("prompt_builder_tool",      "提示词构建", "✍️", "将款式分析结果合成为生图 positive/negative prompt",             "nail",     False, False),
    ("image_generation_tool",    "AI 生图",    "⚡", "调用字节生图 API 进行 inpaint 试戴生成",                         "nail",     False, False),
    ("quality_check_tool",       "质量评分",   "✅", "双图对比评估试戴效果：边界/肤色/光照/款式/自然度",               "nail",     True,  True),
    ("preference_rag_tool",      "偏好记忆",   "💾", "ChromaDB 存储用户喜好款式，支持个性化推荐",                      "nail",     False, False),
    ("trend_query_tool",         "趋势查询",   "📈", "查询近 N 天款式热度信号排行榜",                                  "nail",     False, False),
    ("trend_discovery_tool",     "趋势洞察",   "🔥", "综合趋势数据，LLM 生成爆款洞察报告",                            "nail_ops", True,  False),
    ("ops_analysis_tool",        "运营方案",   "📋", "基于趋势和历史记忆生成可执行营销方案",                           "nail_ops", True,  False),
    ("customer_service_tool",    "智能客服",   "💬", "多轮客服对话，回答预约/价格/售后问题",                          "nail_ops", True,  False),
    ("action_proposal_tool",     "方案提案",   "🔔", "将运营方案写入 DB，等待人工确认后执行",                          "nail_ops", False, False),
    ("evaluation_tool",          "自动评分",   "🏆", "按赛题评分标准对本次运行自动打分",                               "nail_dev", True,  False),
]

_BUILTIN_TOOL_META = [
    ("web_search", "🌐", "网页搜索", "DuckDuckGo 网页搜索，无需 API Key",    "web"),
    ("web_fetch",  "📥", "网页抓取", "抓取并解析网页内容",                    "web"),
    ("file:read",  "📄", "文件读取", "读取本地文件内容",                       "file"),
    ("file:write", "💾", "文件写入", "写入或创建本地文件",                     "file"),
    ("bash",       "🖥️", "命令执行", "在沙箱中执行 bash 命令",               "bash"),
]


@router.get("/tools")
@require_auth
async def list_tools(request: Request):
    """列出所有工具（含开关状态和模型覆盖）。"""
    with _get_db() as conn:
        overrides = {
            r["tool_name"]: {
                "model_name": r["model_name"],
                "is_enabled": bool(r["is_enabled"]),
                "enabled_pages": r["enabled_pages"],
            }
            for r in conn.execute(
                "SELECT tool_name, model_name, is_enabled, enabled_pages FROM nail_tool_overrides"
            ).fetchall()
        }

    nail_tools = []
    for name, display_name, emoji, desc, group, req_llm, req_vision in _NAIL_TOOL_META:
        ov = overrides.get(name, {})
        nail_tools.append({
            "name": name,
            "display_name": display_name,
            "emoji": emoji,
            "description": desc,
            "group": group,
            "requires_llm": req_llm,
            "requires_vision": req_vision,
            "is_enabled": ov.get("is_enabled", True),
            "model_override": ov.get("model_name"),
            "enabled_pages": _safe_parse_pages(ov.get("enabled_pages")),
        })

    builtin_tools = []
    for name, emoji, display_name, desc, group in _BUILTIN_TOOL_META:
        ov = overrides.get(name, {})
        builtin_tools.append({
            "name": name,
            "display_name": display_name,
            "emoji": emoji,
            "description": desc,
            "group": group,
            "requires_llm": False,
            "requires_vision": False,
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
            updates: dict = {}
            if body.model_name is not None:
                updates["model_name"] = body.model_name
            if body.is_enabled is not None:
                updates["is_enabled"] = int(body.is_enabled)
            if body.enabled_pages is not None:
                updates["enabled_pages"] = json.dumps(body.enabled_pages)
            if updates:
                updates["updated_at"] = now
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE nail_tool_overrides SET {set_clause} WHERE tool_name = ?",
                    list(updates.values()) + [tool_name],
                )
        else:
            conn.execute(
                "INSERT INTO nail_tool_overrides (tool_name, model_name, is_enabled, enabled_pages, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    tool_name,
                    body.model_name,
                    int(body.is_enabled) if body.is_enabled is not None else 1,
                    json.dumps(body.enabled_pages) if body.enabled_pages is not None else None,
                    now,
                ),
            )
        conn.commit()
    return {"message": "更新成功"}


# ─── Page-mode 配置 ───────────────────────────────────────────

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
