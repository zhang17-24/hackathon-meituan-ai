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
        {"total_users": n, "top_styles": [...], "signal_summary_7d": {...}, "message": "..."}
    """
    try:
        with get_db() as conn:
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

            user_count = conn.execute(
                "SELECT COUNT(DISTINCT user_id) as cnt FROM nail_user_prefs"
            ).fetchone()

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
        total_users = user_count["cnt"] if user_count else 0

        return json.dumps({
            "total_users": total_users,
            "top_styles": top_styles_data,
            "signal_summary_7d": signal_data,
            "message": f"分析了 {total_users} 名用户的偏好数据",
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("UserPrefAnalytics failed: %s", e)
        return json.dumps({"total_users": 0, "top_styles": [], "signal_summary_7d": {}, "error": str(e)})
