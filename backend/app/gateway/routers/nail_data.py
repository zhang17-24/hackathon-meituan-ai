# backend/app/gateway/routers/nail_data.py
"""nailflow 数据中心 — 自然语言查询接口。"""
import json
import logging
import re
import sqlite3
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.gateway.authz import require_auth
from packages.harness.nailflow.tools.nail.base import get_db, DB_PATH

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nail/data", tags=["nail-data"])

_ROLE_REQUIRED = {"ops", "dev"}
_MAX_ROWS = 1000

_TABLE_SCHEMAS: dict[str, list[dict[str, str]]] = {
    "nail_runs": [
        {"col": "id", "type": "TEXT", "note": "run 主键"},
        {"col": "user_id", "type": "TEXT", "note": "用户ID"},
        {"col": "nail_role", "type": "TEXT", "note": "user/ops/dev"},
        {"col": "intent", "type": "TEXT", "note": "试戴/运营分析/评分"},
        {"col": "status", "type": "TEXT", "note": "running/completed/failed"},
        {"col": "created_at", "type": "DATETIME", "note": "创建时间"},
    ],
    "tool_call_log": [
        {"col": "id", "type": "TEXT", "note": "主键"},
        {"col": "run_id", "type": "TEXT", "note": "关联 nail_runs.id"},
        {"col": "tool_name", "type": "TEXT", "note": "工具名"},
        {"col": "call_index", "type": "INTEGER", "note": "调用序号"},
        {"col": "input_json", "type": "TEXT", "note": "输入 JSON"},
        {"col": "output_json", "type": "TEXT", "note": "输出 JSON"},
        {"col": "thinking", "type": "TEXT", "note": "Agent思考过程"},
        {"col": "duration_ms", "type": "INTEGER", "note": "耗时(毫秒)"},
        {"col": "created_at", "type": "TEXT", "note": "创建时间"},
    ],
    "nail_assets": [
        {"col": "id", "type": "TEXT", "note": "主键"},
        {"col": "run_id", "type": "TEXT", "note": "关联 nail_runs.id"},
        {"col": "asset_type", "type": "TEXT", "note": "hand/style/mask/result"},
        {"col": "file_path", "type": "TEXT", "note": "文件路径"},
        {"col": "created_at", "type": "DATETIME", "note": "创建时间"},
    ],
    "ops_signals": [
        {"col": "id", "type": "INTEGER", "note": "自增主键"},
        {"col": "user_id", "type": "TEXT", "note": "用户ID"},
        {"col": "style_id", "type": "TEXT", "note": "款式ID"},
        {"col": "signal_type", "type": "TEXT", "note": "click/save/order/search"},
        {"col": "created_at", "type": "DATETIME", "note": "信号时间"},
    ],
    "action_proposals": [
        {"col": "id", "type": "TEXT", "note": "提案主键"},
        {"col": "run_id", "type": "TEXT", "note": "关联 nail_runs.id"},
        {"col": "title", "type": "TEXT", "note": "方案标题"},
        {"col": "content", "type": "TEXT", "note": "方案内容(JSON)"},
        {"col": "status", "type": "TEXT", "note": "pending/approved/rejected"},
        {"col": "created_at", "type": "DATETIME", "note": "创建时间"},
        {"col": "confirmed_at", "type": "DATETIME", "note": "确认时间"},
    ],
    "ops_memory": [
        {"col": "id", "type": "INTEGER", "note": "自增主键"},
        {"col": "memory_type", "type": "TEXT", "note": "marketing/feedback/risk"},
        {"col": "content", "type": "TEXT", "note": "记忆内容"},
        {"col": "created_at", "type": "DATETIME", "note": "创建时间"},
    ],
    "evaluation_results": [
        {"col": "id", "type": "TEXT", "note": "主键"},
        {"col": "run_id", "type": "TEXT", "note": "关联 nail_runs.id"},
        {"col": "total_score", "type": "INTEGER", "note": "总分"},
        {"col": "rubric_scores", "type": "TEXT", "note": "分项分(JSON)"},
        {"col": "blocking_issues", "type": "TEXT", "note": "阻塞问题"},
        {"col": "next_dev_tasks", "type": "TEXT", "note": "下一步任务"},
        {"col": "created_at", "type": "DATETIME", "note": "创建时间"},
    ],
    "nail_user_prefs": [
        {"col": "user_id", "type": "TEXT", "note": "用户ID(主键)"},
        {"col": "pref_vector", "type": "TEXT", "note": "偏好向量(JSON)"},
        {"col": "trial_count", "type": "INTEGER", "note": "试戴次数"},
        {"col": "save_count", "type": "INTEGER", "note": "收藏次数"},
        {"col": "updated_at", "type": "TEXT", "note": "更新时间"},
    ],
    "nail_user_prefs_v2": [
        {"col": "user_id", "type": "TEXT", "note": "用户ID(主键)"},
        {"col": "pref_vector", "type": "TEXT", "note": "主偏好向量(JSON)"},
        {"col": "color_vector", "type": "TEXT", "note": "颜色向量(JSON)"},
        {"col": "pattern_vector", "type": "TEXT", "note": "图案向量(JSON)"},
        {"col": "style_tags", "type": "TEXT", "note": "风格标签(JSON)"},
        {"col": "occasion_tags", "type": "TEXT", "note": "场合标签(JSON)"},
        {"col": "skin_tone_hex", "type": "TEXT", "note": "肤色"},
        {"col": "hand_shape", "type": "TEXT", "note": "手型"},
        {"col": "trial_count", "type": "INTEGER", "note": "试戴次数"},
        {"col": "save_count", "type": "INTEGER", "note": "收藏次数"},
        {"col": "updated_at", "type": "TEXT", "note": "更新时间"},
    ],
    "nail_style_catalog": [
        {"col": "style_id", "type": "TEXT", "note": "款式ID(主键)"},
        {"col": "description", "type": "TEXT", "note": "款式描述"},
        {"col": "category", "type": "TEXT", "note": "分类"},
        {"col": "color_tags", "type": "TEXT", "note": "颜色标签"},
        {"col": "image_path", "type": "TEXT", "note": "图片路径"},
        {"col": "source", "type": "TEXT", "note": "static/user"},
    ],
    "nail_hand_photos": [
        {"col": "id", "type": "TEXT", "note": "主键"},
        {"col": "user_id", "type": "TEXT", "note": "用户ID"},
        {"col": "filename", "type": "TEXT", "note": "文件名"},
        {"col": "file_path", "type": "TEXT", "note": "文件路径"},
        {"col": "is_active", "type": "INTEGER", "note": "是否有效"},
        {"col": "created_at", "type": "TEXT", "note": "创建时间"},
    ],
    "nail_style_images": [
        {"col": "id", "type": "TEXT", "note": "主键"},
        {"col": "user_id", "type": "TEXT", "note": "用户ID"},
        {"col": "filename", "type": "TEXT", "note": "文件名"},
        {"col": "file_path", "type": "TEXT", "note": "文件路径"},
        {"col": "category", "type": "TEXT", "note": "分类"},
        {"col": "tags", "type": "TEXT", "note": "标签(JSON)"},
        {"col": "source", "type": "TEXT", "note": "system/user"},
        {"col": "is_active", "type": "INTEGER", "note": "是否有效"},
        {"col": "created_at", "type": "TEXT", "note": "创建时间"},
    ],
    "nail_model_configs": [
        {"col": "id", "type": "TEXT", "note": "主键"},
        {"col": "name", "type": "TEXT", "note": "模型名(唯一)"},
        {"col": "display_name", "type": "TEXT", "note": "显示名"},
        {"col": "provider", "type": "TEXT", "note": "提供商"},
        {"col": "model_id", "type": "TEXT", "note": "模型ID"},
        {"col": "api_base", "type": "TEXT", "note": "API地址"},
        {"col": "supports_vision", "type": "INTEGER", "note": "是否支持视觉"},
        {"col": "created_at", "type": "DATETIME", "note": "创建时间"},
    ],
    "nail_agent_configs": [
        {"col": "config_key", "type": "TEXT", "note": "main_agent/tool_default"},
        {"col": "model_name", "type": "TEXT", "note": "绑定的模型名"},
        {"col": "updated_at", "type": "DATETIME", "note": "更新时间"},
    ],
    "nail_tool_overrides": [
        {"col": "tool_name", "type": "TEXT", "note": "工具名(主键)"},
        {"col": "model_name", "type": "TEXT", "note": "覆盖的模型名"},
        {"col": "is_enabled", "type": "INTEGER", "note": "是否启用"},
        {"col": "updated_at", "type": "DATETIME", "note": "更新时间"},
    ],
}


def _build_schema_context() -> str:
    lines = ["-- SQLite 表结构（只读查询，禁止 INSERT/UPDATE/DELETE/DROP/ALTER）"]
    for table, cols in _TABLE_SCHEMAS.items():
        col_strs = [f"  {c['col']} {c['type']} -- {c['note']}" for c in cols]
        lines.append(f"\nCREATE TABLE {table} (")
        lines.extend(col_strs)
        lines.append(");")
    return "\n".join(lines)


def _is_readonly_sql(sql: str) -> bool:
    cleaned = sql.strip().upper()
    if not any(cleaned.startswith(p) for p in ("SELECT", "WITH", "EXPLAIN")):
        return False
    forbidden = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH", "DETACH", "PRAGMA", "REPLACE"}
    tokens = set(re.findall(r'\b[A-Z]+\b', cleaned))
    if tokens & forbidden:
        return False
    return True


def _execute_query(sql: str) -> tuple[list[str], list[list[Any]]]:
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA query_only = ON")
        cur = conn.execute(sql)
        rows_raw = cur.fetchmany(_MAX_ROWS + 1)
        if len(rows_raw) > _MAX_ROWS:
            rows_raw = rows_raw[:_MAX_ROWS]
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [[_safe_value(v) for v in row] for row in rows_raw]
        return columns, rows
    finally:
        conn.close()


def _safe_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (int, float, str)):
        return v
    if isinstance(v, bytes):
        return f"<BLOB {len(v)} bytes>"
    return str(v)


class QueryRequest(BaseModel):
    question: str


# ─── Endpoints ──────────────────────────────────────────────


@router.get("/schema")
@require_auth
async def get_schema(request: Request):
    nail_role = getattr(request.state.user, "nail_role", "user")
    if nail_role not in _ROLE_REQUIRED:
        raise HTTPException(403, "需要 ops 或 dev 权限")
    return {"tables": _TABLE_SCHEMAS, "db_path": str(DB_PATH)}


@router.post("/query")
@require_auth
async def natural_query(body: QueryRequest, request: Request):
    nail_role = getattr(request.state.user, "nail_role", "user")
    if nail_role not in _ROLE_REQUIRED:
        raise HTTPException(403, "需要 ops 或 dev 权限")

    question = (body.question or "").strip()
    if not question:
        raise HTTPException(400, "问题不能为空")

    schema_ctx = _build_schema_context()

    try:
        from nailflow.models import create_chat_model
        from langchain_core.messages import HumanMessage

        prompt = (
            f"你是 SQLite 专家。根据以下表结构，将用户问题转换为只读 SELECT 语句。\n"
            f"规则：\n"
            f"1. 只允许 SELECT / WITH 查询，禁止任何写操作\n"
            f"2. 限制返回行数用 LIMIT，不超过 500 行\n"
            f"3. COUNT/SUM/AVG 等聚合函数可以使用\n"
            f"4. 只返回一条 SQL 语句，不要注释，不要 markdown 代码块\n"
            f"5. 字符串匹配用 LIKE 或 INSTR，日期筛选用 datetime() 函数\n\n"
            f"{schema_ctx}\n\n"
            f"用户问题：{question}\n\n"
            f"SQL:"
        )
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)
        resp = model.invoke([HumanMessage(content=prompt)])
        sql_raw = resp.content.strip()

        if "```" in sql_raw:
            parts = sql_raw.split("```")
            sql_raw = parts[1] if len(parts) > 1 else sql_raw
            if sql_raw.lower().startswith("sql"):
                sql_raw = sql_raw[3:]
        sql = sql_raw.strip().rstrip(";")

        logger.info("DataQuery SQL generated: %s", sql[:200])
    except Exception as e:
        logger.error("LLM SQL generation failed: %s", e)
        return {
            "question": question,
            "sql": "",
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": f"LLM 生成 SQL 失败: {e}",
        }

    if not _is_readonly_sql(sql):
        return {
            "question": question,
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": "生成的 SQL 包含禁止的操作（仅允许 SELECT），请换种方式提问",
        }

    try:
        columns, rows = _execute_query(sql)
    except Exception as e:
        logger.error("SQL execution failed: %s", e)
        return {
            "question": question,
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "error": f"查询执行失败: {e}",
        }

    return {
        "question": question,
        "sql": sql,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "error": None,
    }
