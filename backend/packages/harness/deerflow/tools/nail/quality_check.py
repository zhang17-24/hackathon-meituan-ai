# backend/packages/harness/deerflow/tools/nail/quality_check.py
"""双图对比评估试戴质量：甲面边界、肤色漂移、款式相似度等维度。"""
import base64
import json
import logging

from langchain.tools import tool
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

_FALLBACK_SCORES = {
    "boundary_score": 5,
    "skin_tone_score": 5,
    "lighting_score": 5,
    "style_match_score": 5,
    "natural_score": 5,
}

_EVAL_PROMPT = """\
You are a nail art try-on quality evaluator. Compare the ORIGINAL hand image and the AI TRY-ON result.

Score each dimension from 0-10:
1. boundary_score: Are nail boundaries clean? No color bleeding onto skin?
2. skin_tone_score: Is skin tone preserved? No drift?
3. lighting_score: Does lighting match the original?
4. style_match_score: Does the nail art match the target style?
5. natural_score: Does it look natural and commercially presentable?

Target style: {style_summary}

Return ONLY valid JSON:
{{
  "scores": {{
    "boundary_score": 8,
    "skin_tone_score": 9,
    "lighting_score": 8,
    "style_match_score": 7,
    "natural_score": 8
  }},
  "overall": 8,
  "fit_comment": "该款式很适合您的手型",
  "risk_comment": "饰品较大，建议到店确认尺寸",
  "adjustments": "可以调整颜色明度",
  "explanation_zh": "我保留了原图的肤色、手纹和光照，只在甲面区域试戴了该款式。整体效果自然，甲面边界清晰。"
}}"""


def _encode(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@tool
def quality_check_tool(
    original_hand_path: str,
    result_path: str,
    style_summary_zh: str = "",
) -> str:
    """评估 AI 试戴效果图质量，返回各维度评分和中文解释。

    Args:
        original_hand_path: 原始手图路径。
        result_path: AI 生成的试戴结果图路径。
        style_summary_zh: 款式中文摘要（来自 prompt_builder_tool），用于评分参考。

    Returns:
        JSON 字符串，字段：
        - scores (dict): 五维评分（0-10）
        - overall (int): 综合评分
        - fit_comment (str): 中文适合度评语
        - risk_comment (str): 中文风险提示
        - adjustments (str): 可调整项
        - explanation_zh (str): 完整中文解释（向用户展示）
    """
    _default_response = {
        "scores": _FALLBACK_SCORES,
        "overall": 5,
        "fit_comment": "效果基本可用",
        "risk_comment": "建议到店实际确认",
        "adjustments": "可进一步调整",
        "explanation_zh": "AI 已完成试戴，质量评估暂不可用，请到店确认实际效果。",
    }

    try:
        from deerflow.models import create_chat_model
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)

        orig_b64 = _encode(original_hand_path)
        res_b64 = _encode(result_path)

        prompt = _EVAL_PROMPT.format(style_summary=style_summary_zh or "not specified")

        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{orig_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{res_b64}"}},
            {"type": "text", "text": prompt},
        ])
        response = model.invoke([msg])
        raw = response.content.strip()

        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        # 确保 overall 字段存在
        if "overall" not in result and "scores" in result:
            result["overall"] = round(sum(result["scores"].values()) / len(result["scores"]))
        return json.dumps(result, ensure_ascii=False)

    except FileNotFoundError as e:
        _default_response["explanation_zh"] = f"图片文件不存在（{e}），跳过质量评估。"
        return json.dumps(_default_response, ensure_ascii=False)
    except Exception as e:
        logger.warning("QualityCheck fallback (LLM unavailable or error): %s", e)
        _default_response["explanation_zh"] = f"质量评估暂时不可用（{type(e).__name__}），请到店确认效果。"
        return json.dumps(_default_response, ensure_ascii=False)
