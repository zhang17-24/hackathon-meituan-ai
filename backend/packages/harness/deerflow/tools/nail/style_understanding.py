# backend/packages/harness/deerflow/tools/nail/style_understanding.py
"""用 LLM Vision 解析款式图，提取像素级颜色/纹理/甲型/饰品/风格标签。"""
import base64
import json
import logging

from langchain.tools import tool
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# ── 超级详细的 vision 分析 prompt ──
_STYLE_ANALYSIS_PROMPT = """You are a professional nail art analyst with expert color perception.

Analyze this nail art reference image and return ONLY valid JSON. Be EXTREMELY precise:

{
  "colors": ["#FF6B8A", "#FFD700"],
  "color_description": "warm rose pink base with metallic gold foil accents on ring finger",
  "texture": "glossy",
  "nail_shape": "almond",
  "decorations": ["gold foil", "tiny pearl at cuticle"],
  "pattern": "solid base, accent nail with full gold foil on ring finger, fine gold line on middle finger",
  "style_tags": ["korean", "elegant", "bridal"],
  "gradient": null,
  "finish": "high gloss top coat",
  "length": "medium",
  "style_description_en": "warm rose pink almond nails with gold foil accent on ring finger, elegant bridal style",
  "style_description_zh": "暖调玫瑰粉杏仁甲，无名指金色箔片点缀，优雅新娘风",
  "level_of_detail": "detailed but clean"
}

RULES:
- colors: List hex codes of ALL visible colors, most dominant first
- color_description: Describe exact shade, warmth/cool, saturation, and placement
- texture: glitter|matte|glossy|gradient|marble|solid|cat_eye|chrome|jelly|velvet
- nail_shape: round|square|almond|coffin|stiletto|oval|ballerina|lipstick
- decorations: List ALL visible decorations (rhinestone, pearl, foil, charm, sticker, glitter, chrome powder)
- pattern: Describe the exact design pattern across all nails. Which nails are accent nails? What's on each?
- gradient: If gradient, describe start color → end color and direction (horizontal/vertical/diagonal)
- finish: high gloss|matte|satin|velvet
- length: short|medium|long|extra long
- style_description_en: ONE detailed English sentence capturing the complete look
- style_description_zh: ONE detailed Chinese sentence

Be as precise as humanly possible. Your description will be used to generate a nearly identical nail art."""


def _encode_image(path: str) -> str:
    from .base import resolve_image_path
    resolved = resolve_image_path(path)
    with open(str(resolved), "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@tool
def style_understanding_tool(style_image_path: str, user_description: str = "") -> str:
    """Analisa gambar nail art reference, ekstrak warna/tekstur/bentuk/dekorasi.

    Args:
        style_image_path: Path ke gambar referensi nail art.
        user_description: Deskripsi tambahan dari user (opsional).

    Returns:
        JSON dengan fields: colors, color_description, texture, nail_shape,
        decorations, pattern, style_tags, style_description_en, style_description_zh
    """
    try:
        from deerflow.models import create_chat_model
        from deerflow.models.router import ModelRouter, Capability

        resolution = ModelRouter.resolve("style_understanding_tool", Capability.VISION)
        if resolution is None:
            return json.dumps({
                "error": "No vision model available. Add a vision-capable model (e.g. qwen-vl-max) in Settings.",
                "colors": [], "color_description": "", "texture": "", "nail_shape": "",
                "decorations": [], "pattern": "", "style_tags": [],
                "style_description_en": "", "style_description_zh": "",
            }, ensure_ascii=False)

        logger.info("StyleUnderstanding using model: %s (source=%s)", resolution.name, resolution.source)
        model = create_chat_model(name=resolution.name, thinking_enabled=False, attach_tracing=False)

        img_b64 = _encode_image(style_image_path)

        prompt = _STYLE_ANALYSIS_PROMPT
        if user_description:
            prompt += f"\n\nUser note: {user_description}"

        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": prompt},
        ])
        response = model.invoke([msg])
        raw = response.content.strip()

        # 去掉可能的 markdown 代码块
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw.strip())
        return json.dumps(result, ensure_ascii=False)

    except FileNotFoundError:
        return json.dumps({
            "error": f"Style image not found: {style_image_path}",
            "colors": [], "color_description": "", "texture": "", "nail_shape": "",
            "decorations": [], "pattern": "", "style_tags": [],
            "style_description_en": "", "style_description_zh": "",
        }, ensure_ascii=False)
    except Exception as e:
        logger.warning("StyleUnderstanding failed: %s", e)
        return json.dumps({
            "error": f"Style analysis failed ({type(e).__name__}): {e}. "
                     "Please add a vision-capable model (e.g. qwen-vl-max) in Settings.",
            "colors": [], "color_description": "", "texture": "", "nail_shape": "",
            "decorations": [], "pattern": "", "style_tags": [],
            "style_description_en": "", "style_description_zh": "",
        }, ensure_ascii=False)
