# backend/packages/harness/nailflow/tools/nail/prompt_builder.py
"""Build image generation prompts from detailed style analysis — with optional RAG augmentation.

RAG 增强模式: 接收款式库中检索到的结构化特征, 注入生图 prompt, 提升款式还原度。
"""

import json
import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)

_NEG_PROMPT_BASE = (
    "do not redraw the hand, do not change skin tone, do not alter fingers, "
    "no extra fingers, no missing fingers, no deformed nails, no floating decorations, "
    "no blurry cuticle, no color bleeding outside nail mask, no background change, "
    "no plastic skin, no overexposure, no cartoon, no painting style"
)

# 图案类型 → 动态负面提示词（防止模型简化图案）
_PATTERN_NEGATIVES = {
    "cow": "no round dots, no solid french only, no gradient, no polka dots, "
           "pattern MUST be irregular organic blotches like Holstein cow hide",
    "dot": "no irregular blobs, dots MUST be precisely round and evenly sized",
    "stripe": "no irregular wavy lines, stripes MUST be clean parallel lines",
    "marble": "no geometric patterns, veins MUST branch organically like natural stone",
    "floral": "no abstract blobs, flowers MUST have visible petal structure",
    "french": "tip line MUST be a thin 2mm curved line at free edge only, "
              "NOT a thick block, NOT a gradient band, NOT covering half the nail",
    "glitter": "no large chunks, glitter MUST be fine particles with random light reflections",
    "gradient": "no hard edges, transition MUST be smooth and continuous",
    "leopard": "no cow spots, spots MUST be irregular rings with darker borders",
    "plaid": "no random intersecting lines, lines MUST form proper grid pattern",
    "solid": "no patterns, no decorations, MUST be perfectly even single color",
}


def _build_dynamic_negatives(pattern_desc: str = "", patterns_from_rag: list[str] | None = None) -> str:
    """根据图案类型生成动态负面提示词。"""
    extra = []
    if patterns_from_rag:
        for p in patterns_from_rag:
            for keyword, neg in _PATTERN_NEGATIVES.items():
                if keyword in p.lower() and neg not in " ".join(extra):
                    extra.append(neg)

    if not extra and pattern_desc:
        for keyword, neg in _PATTERN_NEGATIVES.items():
            if keyword in pattern_desc.lower() and neg not in " ".join(extra):
                extra.append(neg)

    if extra:
        return _NEG_PROMPT_BASE + ". DO NOT SIMPLIFY THE PATTERN: " + " | ".join(extra)
    return _NEG_PROMPT_BASE


@tool
def prompt_builder_tool(
    style_analysis_json: str,
    user_request: str = "",
    rag_styles_json: str = "",
) -> str:
    """Build detailed positive/negative prompts for the inpaint image generation model.

    RAG 增强模式：传入 rag_styles_json（image_search_tool 或 nail_style_recommend_tool 的结果），
    将款式库中的结构化特征注入 prompt，大幅提升款式还原精度。

    Args:
        style_analysis_json: JSON output of style_understanding_tool.
        user_request: Optional extra user text requirements.
        rag_styles_json: Optional RAG search results for augmentation.
            Should be the JSON output of image_search_tool or nail_style_recommend_tool.

    Returns:
        JSON: positive_prompt, negative_prompt, style_summary_zh, style_tags, rag_augmented(bool)
    """
    try:
        style = json.loads(style_analysis_json)

        # ── 解析 RAG 增强数据 ──
        rag_patterns = []
        rag_descriptions = []
        rag_augmented = False
        if rag_styles_json:
            try:
                rag_data = json.loads(rag_styles_json)
                rag_items = rag_data.get("matches") or rag_data.get("recommendations") or []
                for item in rag_items[:3]:
                    if item.get("description"):
                        rag_descriptions.append(item["description"])
                    cat = item.get("category", "")
                    if cat:
                        rag_patterns.append(cat)
                if rag_descriptions:
                    rag_augmented = True
            except (json.JSONDecodeError, TypeError):
                pass

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

        # ── 构建正向 prompt ──
        parts = [
            "Edit ONLY the fingernail regions inside the provided nail mask.",
            "Preserve original hand: skin tone, wrinkles, joints, shadows, background, camera angle, lighting.",
        ]

        # RAG 增强: 注入库中款式的描述特征
        if rag_augmented and rag_descriptions:
            rag_context = "; ".join(rag_descriptions[:2])
            parts.append(f"Reference nail styles from catalog (for design precision): {rag_context}.")

        # 款式描述
        if style_desc_en:
            parts.append(f"Apply this nail art style: {style_desc_en}.")
        if color_desc:
            parts.append(f"Color details: {color_desc}.")
        elif colors:
            parts.append(f"Use COLORS exactly: {', '.join(colors)}.")

        # 从 RAG 结果中提取颜色参考
        if rag_augmented and rag_items and not color_desc:
            rag_colors = [item.get("color_tags", "") for item in rag_items[:3] if item.get("color_tags")]
            if rag_colors:
                parts.append(f"Color reference from catalog: {', '.join(rag_colors)}.")

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

        # ── 动态负面提示词 ──
        negative = _build_dynamic_negatives(pattern, rag_patterns)

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
        if rag_augmented:
            zh += f" [RAG增强: {len(rag_descriptions)}条参考]"

        return json.dumps({
            "positive_prompt": positive,
            "negative_prompt": negative,
            "style_summary_zh": zh,
            "style_tags": style_tags,
            "rag_augmented": rag_augmented,
        }, ensure_ascii=False)

    except Exception as e:
        logger.warning("PromptBuilder fallback: %s", e)
        desc = user_request or "beautiful natural nail art"
        return json.dumps({
            "positive_prompt": (
                f"Edit only the fingernail regions inside the provided nail mask. "
                f"Preserve the original hand. Apply: {desc}. Photorealistic, 4k."
            ),
            "negative_prompt": _NEG_PROMPT_BASE,
            "style_summary_zh": user_request or "自然美甲",
            "rag_augmented": False,
        }, ensure_ascii=False)
