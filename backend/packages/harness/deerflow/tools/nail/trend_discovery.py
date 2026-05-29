# backend/packages/harness/deerflow/tools/nail/trend_discovery.py
"""综合趋势分析：读取信号数据，用 LLM 生成洞察报告（OpenClaw 检索模式）。"""
import json
import logging

from langchain.tools import tool
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


@tool
def trend_discovery_tool(days: int = 7) -> str:
    """分析近期美甲款式趋势，生成爆款洞察报告和运营建议。

    Args:
        days: 分析窗口天数，默认 7。

    Returns:
        JSON 字符串，字段：
        - hot_styles (list): 爆款列表，每项含 style_id/reason/suggested_action
        - cold_styles (list): 冷门款列表
        - trend_summary (str): 趋势摘要
        - action_hints (list): 具体运营建议
        - data_source (str): 数据来源标注
    """
    try:
        from .trend_query import trend_query_tool
        trend_raw = trend_query_tool.run({"days": days, "top_n": 20})
        trend_data = json.loads(trend_raw)
        trending = trend_data.get("trending_styles", [])

        hot = [s for s in trending if s["total_signals"] >= 3]
        cold = [s for s in trending if s["total_signals"] <= 1]

        # LLM 生成洞察（降级时用规则）
        try:
            from deerflow.models import create_chat_model
            model = create_chat_model(thinking_enabled=False, attach_tracing=False)

            prompt = (
                f"你是美甲门店运营分析师。根据以下 {days} 天的款式数据生成洞察报告（返回 JSON）：\n"
                f"热门款式（信号数≥3）：{json.dumps(hot[:5], ensure_ascii=False)}\n"
                f"冷门款式（信号数≤1）：{json.dumps(cold[:3], ensure_ascii=False)}\n"
                '返回格式：{"hot_styles":[{"style_id":"...","reason":"...","suggested_action":"..."}],'
                '"cold_styles":[{"style_id":"...","reason":"...","suggested_action":"..."}],'
                '"trend_summary":"一段话总结","action_hints":["具体建议1","具体建议2"]}'
            )
            resp = model.invoke([HumanMessage(content=prompt)])
            raw = resp.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw.strip())
        except Exception as llm_err:
            logger.warning("TrendDiscovery LLM fallback: %s", llm_err)
            result = {
                "hot_styles": [{"style_id": s["style_id"], "reason": f"近{days}天信号数{s['total_signals']}", "suggested_action": "做限时套餐"} for s in hot[:3]],
                "cold_styles": [{"style_id": s["style_id"], "reason": "信号较少", "suggested_action": "换封面或降价"} for s in cold[:2]],
                "trend_summary": f"本周追踪 {len(trending)} 个款式，{'，'.join(s['style_id'] for s in hot[:3])} 表现突出",
                "action_hints": ["对热门款做限时套餐", "对冷门款换主图或降价处理"],
            }

        result["data_source"] = f"来自近 {days} 日收藏/订单/点击信号"
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        logger.error("TrendDiscovery failed: %s", e)
        return json.dumps({"error": str(e), "hot_styles": [], "cold_styles": [], "trend_summary": "分析失败", "action_hints": []})
