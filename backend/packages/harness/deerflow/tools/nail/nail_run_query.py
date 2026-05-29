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
        {"runs": [...], "count": n}
        每个 run 包含：run_id, nail_role, status, created_at,
        total_duration_ms, tool_chain, thinking_log, tool_count
    """
    try:
        limit = min(int(limit), 10)

        with get_db() as conn:
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
                calls = conn.execute(
                    "SELECT tool_name, call_index, duration_ms, thinking "
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
                    "run_id":            run_id,
                    "nail_role":         run["nail_role"],
                    "status":            run["status"],
                    "created_at":        run["created_at"],
                    "total_duration_ms": total_ms,
                    "tool_chain":        tool_chain,
                    "thinking_log":      thinking_log,
                    "tool_count":        len(tool_chain),
                })

        return json.dumps({"runs": result_runs, "count": len(result_runs)}, ensure_ascii=False)

    except Exception as e:
        logger.error("NailRunQuery failed: %s", e)
        return json.dumps({"runs": [], "count": 0, "error": str(e)})
