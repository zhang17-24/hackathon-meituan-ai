# backend/packages/harness/deerflow/tools/nail/prompt_builder.py
"""Build image generation prompts from detailed style analysis. """
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


@tool
def prompt_builder_tool(style_analysis_json: str, user_request: str = "") -> str:
    """Build detailed positive/negative prompts for the inpaint image generation model.

    Args:
        style_analysis_json: JSON output of style_understanding_tool.
        user_request: Optional extra user text requirements.

    Returns:
        JSON: positive_prompt, negative_prompt, style_summary_zh
    """
    try:
        style = json.loads(style_analysis_json)

        # 颜色
        colors = style.get("colors", [])
        color_desc = style.get("color_description", "")

        # 质感和甲型
        texture = style.get("texture", "glossy")
        nail_shape = style.get("nail_shape", "round")
        finish = style.get("finish", "")
        length = style.get("length", "medium")

        # 图案和饰品
        pattern = style.get("pattern", "")
        decorations = style.get("decorations", [])
        gradient = style.get("gradient")
        style_desc_en = style.get("style_description_en", "")
        style_tags = style.get("style_tags", [])

        # ── 构建超级详细的正向 prompt ──
        parts = [
            "Edit ONLY the fingernail regions inside the provided nail mask.",
            "Preserve original hand: skin tone, wrinkles, joints, shadows, background, camera angle, lighting.",
        ]

        # 款式描述
        if style_desc_en:
            parts.append(f"Apply this nail art style: {style_desc_en}.")
        if color_desc:
            parts.append(f"Color details: {color_desc}.")
        elif colors:
            parts.append(f"Use COLORS exactly: {', '.join(colors)}.")

        # 质感
        texture_map = {
            "cat_eye": "magnetic cat eye effect with a bright reflective line across the nail",
            "chrome": "mirror chrome metallic finish with high reflectivity",
            "jelly": "translucent jelly/sheer glass-like finish",
            "velvet": "soft velvet/matte suede texture",
            "glitter": "sparkling glitter particles evenly distributed",
            "matte": "flat matte finish, no shine",
            "glossy": "high-shine glossy top coat",
            "gradient": "smooth gradient/ombré transition",
            "marble": "marble stone texture with natural veins",
            "solid": "solid even color, no texture",
        }
        texture_desc = texture_map.get(texture, texture)
        parts.append(f"Texture: {texture_desc}.")

        # 甲型
        parts.append(f"Nail shape: {nail_shape}, length: {length}.")

        # 图案
        if pattern:
            parts.append(f"Design pattern: {pattern}.")

        # 渐变
        if gradient and isinstance(gradient, dict):
            g_from = gradient.get("from", "")
            g_to = gradient.get("to", "")
            g_dir = gradient.get("direction", "vertical")
            if g_from and g_to:
                parts.append(f"Gradient: {g_from} to {g_to}, direction {g_dir}.")

        # 饰品
        if decorations:
            decoration_str = ", ".join(decorations)
            parts.append(f"Decorations on nails: {decoration_str}. Place them precisely as described in the reference.")

        # 质感收尾
        if finish:
            parts.append(f"Finish: {finish}.")

        parts.append("Clean cuticle edges. Realistic commercial beauty product photo. 4k. Natural lighting.")

        positive = " ".join(parts)

        # ── 中文摘要 ──
        zh = style.get("style_description_zh", "")
        if not zh:
            zh_parts = []
            if color_desc:
                zh_parts.append(color_desc)
            if texture:
                zh_parts.append(texture)
            if nail_shape:
                zh_parts.append(f"{nail_shape}甲型")
            zh = "，".join(zh_parts) if zh_parts else style_desc_en
        if user_request:
            zh += f"（用户要求：{user_request}）"

        return json.dumps({
            "positive_prompt": positive,
            "negative_prompt": _NEG_PROMPT,
            "style_summary_zh": zh,
            "style_tags": style_tags,
        }, ensure_ascii=False)

    except Exception as e:
        logger.warning("PromptBuilder fallback: %s", e)
        desc = user_request or "beautiful natural nail art"
        return json.dumps({
            "positive_prompt": (
                f"Edit only the fingernail regions inside the provided nail mask. "
                f"Preserve the original hand. Apply: {desc}. Photorealistic, 4k."
            ),
            "negative_prompt": _NEG_PROMPT,
            "style_summary_zh": user_request or "自然美甲",
        }, ensure_ascii=False)
