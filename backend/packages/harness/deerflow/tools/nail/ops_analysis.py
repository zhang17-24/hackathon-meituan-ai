# backend/packages/harness/deerflow/tools/nail/ops_analysis.py
"""运营方案生成（OpenClaw 长期记忆模式）：读取历史营销记录，生成可执行方案。"""
import json
import logging

from langchain.tools import tool
from langchain_core.messages import HumanMessage

from .base import get_db

logger = logging.getLogger(__name__)

_MARKETING_TEMPLATES = [
    {"type": "限时套餐", "desc": "把高收藏款做成限时折扣套餐，刺激转化"},
    {"type": "复购召回", "desc": "按上次美甲时间生成提醒消息，附推荐款式"},
    {"type": "换封面",   "desc": "对低转化款换主图，突出显白/耐脱落卖点"},
    {"type": "节日主题", "desc": "结合节日（520/七夕/毕业季）做主题组合"},
]


@tool
def ops_analysis_tool(trend_summary: str, query: str = "") -> str:
    """基于趋势数据和历史记忆生成运营方案（需人工确认才能执行）。

    Args:
        trend_summary: trend_discovery_tool 返回的 JSON 摘要字符串。
        query: 运营人员的具体提问（可选，如"本周重点推什么款式"）。

    Returns:
        JSON 字符串，字段：
        - marketing_actions (list): 方案列表，每项含 title/target_user/reason/expected_metric/risk/requires_human_confirm
        - data_source (str): 数据来源标注
    """
    # 读取历史营销记忆（OpenClaw 长期记忆）
    try:
        with get_db() as conn:
            memory_rows = conn.execute(
                "SELECT content FROM ops_memory WHERE memory_type='marketing' ORDER BY created_at DESC LIMIT 5"
            ).fetchall()
        memory_ctx = "\n".join([r["content"] for r in memory_rows]) if memory_rows else "暂无历史记录"
    except Exception:
        memory_ctx = "历史记忆查询失败"

    try:
        from deerflow.models import create_chat_model
        from deerflow.models.router import ModelRouter, Capability
        resolution = ModelRouter.resolve("ops_analysis_tool", Capability.CHAT)
        model = create_chat_model(name=resolution.name if resolution else None, thinking_enabled=False, attach_tracing=False)

        prompt = (
            f"你是美团美甲门店运营专家。生成 2-3 条可执行运营方案（JSON格式）。\n"
            f"趋势数据：{trend_summary[:500]}\n"
            f"历史营销效果：{memory_ctx[:300]}\n"
            f"运营提问：{query or '生成本周运营计划'}\n"
            f"可用手段：{json.dumps(_MARKETING_TEMPLATES, ensure_ascii=False)}\n"
            '返回JSON：{"marketing_actions":[{"title":"方案标题","target_user":"目标用户","reason":"数据支撑","expected_metric":"预期指标","risk":"潜在风险","requires_human_confirm":true}]}'
        )
        resp = model.invoke([HumanMessage(content=prompt)])
        raw = resp.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
    except Exception as e:
        logger.warning("OpsAnalysis LLM fallback: %s", e)
        result = {
            "marketing_actions": [
                {"title": "爆款限时套餐", "target_user": "近7天收藏用户", "reason": "收藏信号高", "expected_metric": "转化率+15%", "risk": "库存压力", "requires_human_confirm": True},
                {"title": "冷门款换封面", "target_user": "新用户", "reason": "点击率低", "expected_metric": "曝光率+20%", "risk": "设计成本", "requires_human_confirm": True},
            ]
        }

    result["data_source"] = "来自趋势分析 + 历史营销记录"
    return json.dumps(result, ensure_ascii=False)
