# backend/packages/harness/deerflow/tools/nail/trend_query.py
"""查询指定天数内款式热度信号，返回爆款榜。"""
import json
import logging

from langchain.tools import tool

from .base import get_db

logger = logging.getLogger(__name__)


@tool
def trend_query_tool(days: int = 7, top_n: int = 10) -> str:
    """查询近期美甲款式热度排行。

    Args:
        days: 统计窗口天数，默认 7。
        top_n: 返回排行前 N 名，默认 10。

    Returns:
        JSON 字符串，字段：
        - days (int): 查询窗口
        - trending_styles (list): 排行榜，每项含 style_id/total_signals/saves/orders/clicks
        - total_styles_tracked (int): 追踪款式总数
    """
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT
                    style_id,
                    COUNT(*)                                                   AS total_signals,
                    SUM(CASE WHEN signal_type = 'save'  THEN 1 ELSE 0 END)   AS saves,
                    SUM(CASE WHEN signal_type = 'order' THEN 1 ELSE 0 END)   AS orders,
                    SUM(CASE WHEN signal_type = 'click' THEN 1 ELSE 0 END)   AS clicks
                FROM ops_signals
                WHERE created_at >= datetime('now', ?)
                GROUP BY style_id
                ORDER BY total_signals DESC
                LIMIT ?
            """, (f"-{days} day", top_n)).fetchall()

        trending = [dict(r) for r in rows]

        return json.dumps({
            "days": days,
            "trending_styles": trending,
            "total_styles_tracked": len(trending),
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("TrendQuery failed: %s", e)
        return json.dumps({
            "days": days,
            "trending_styles": [],
            "total_styles_tracked": 0,
            "error": str(e),
        })
