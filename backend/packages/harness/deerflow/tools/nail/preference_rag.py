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
        data: action=save 时信号类型："tryon"/"save"/"search"。

    Returns:
        action=save: {"saved": true, "signal_type": "..."}
        action=get_stats: {"trial_count": n, "save_count": n, "has_preference": bool}
        失败时: {"error": "...", "saved": false}
    """
    try:
        if action == "save":
            signal_type = data if data in ("tryon", "save", "search") else "tryon"
            update_user_pref_vector(user_id, style_id, signal_type)
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
