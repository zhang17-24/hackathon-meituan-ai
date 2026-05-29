# backend/packages/harness/deerflow/tools/nail/prompt_builder.py
"""根据款式分析和用户需求，构建生图模型的 positive/negative prompt。"""
import json
import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)

_NEG_PROMPT = (
    "do not redraw the hand, do not change skin tone, do not alter fingers, "
    "no extra fingers, no missing fingers, no deformed nails, no floating decorations, "
    "no blurry cuticle, no color bleeding outside nail mask, no background change, "
    "no plastic skin, no overexposure, no cartoon, no painting style"
)

_POS_TEMPLATE = (
    "Edit only the fingernail regions inside the provided nail mask. "
    "Preserve the original hand skin tone, wrinkles, joints, shadows, "
    "background, camera angle, and lighting. "
    "Apply the nail art style: {style_description}{user_mod}. "
    "Colors: {colors}. Texture: {texture}. Nail shape: {nail_shape}. "
    "{decoration_str}"
    "Clean cuticle edges, realistic gloss, no changes outside the nails. "
    "Photorealistic commercial beauty retouching, natural hand photo, 4k quality."
)


@tool
def prompt_builder_tool(style_analysis_json: str, user_request: str = "") -> str:
    """根据款式分析 JSON 和用户需求构建生图 prompt。

    Args:
        style_analysis_json: style_understanding_tool 的输出 JSON 字符串。
        user_request: 用户额外文字要求（可选，如"我想要暗一点"）。

    Returns:
        JSON 字符串，字段：
        - positive_prompt (str): 生图正向 prompt（英文）
        - negative_prompt (str): 生图反向 prompt（英文）
        - style_summary_zh (str): 中文款式摘要（展示给用户）
    """
    try:
        style = json.loads(style_analysis_json)

        colors = ", ".join(style.get("colors", ["neutral"]))
        texture = style.get("texture", "glossy")
        nail_shape = style.get("nail_shape", "round")
        decorations = style.get("decorations", [])
        style_desc = style.get("style_description_en", "nail polish")
        style_tags = style.get("style_tags", [])

        decoration_str = (f"Decorations: {', '.join(decorations)}. ") if decorations else ""
        user_mod = (f" User preference: {user_request}") if user_request else ""

        positive = _POS_TEMPLATE.format(
            style_description=style_desc,
            user_mod=user_mod,
            colors=colors,
            texture=texture,
            nail_shape=nail_shape,
            decoration_str=decoration_str,
        )

        zh_parts = [f"款式：{style_desc}", f"颜色：{colors}", f"质感：{texture}", f"甲型：{nail_shape}"]
        if style_tags:
            zh_parts.append(f"风格：{'/'.join(style_tags)}")
        if user_request:
            zh_parts.append(f"用户要求：{user_request}")
        summary_zh = "，".join(zh_parts)

        return json.dumps({
            "positive_prompt": positive,
            "negative_prompt": _NEG_PROMPT,
            "style_summary_zh": summary_zh,
        }, ensure_ascii=False)

    except Exception as e:
        logger.warning("PromptBuilder fallback (parse/format error): %s", e)
        desc = user_request or "beautiful natural nail art"
        return json.dumps({
            "positive_prompt": (
                f"Edit only the fingernail regions inside the provided nail mask. "
                f"Preserve the original hand. Apply: {desc}. Photorealistic."
            ),
            "negative_prompt": _NEG_PROMPT,
            "style_summary_zh": user_request or "自然美甲",
        }, ensure_ascii=False)
