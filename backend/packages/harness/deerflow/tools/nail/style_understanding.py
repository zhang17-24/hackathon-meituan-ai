# backend/packages/harness/deerflow/tools/nail/style_understanding.py
"""用 LLM Vision 解析款式图，提取颜色/纹理/甲型/饰品/风格标签。"""
import base64
import json
import logging
from pathlib import Path

from langchain.tools import tool
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

_FALLBACK = {
    "colors": ["pink"],
    "texture": "glossy",
    "nail_shape": "round",
    "decorations": [],
    "style_tags": ["solid"],
    "style_description_en": "glossy pink nail polish, solid color",
}


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@tool
def style_understanding_tool(style_image_path: str, user_description: str = "") -> str:
    """解析美甲款式图，提取风格标签和英文描述（供生图模型使用）。

    Args:
        style_image_path: 款式参考图的本地路径。
        user_description: 用户对目标款式的补充文字描述（可选）。

    Returns:
        JSON 字符串，字段：
        - colors (list): 主色列表（英文色名）
        - texture (str): glitter/matte/glossy/gradient/marble/solid
        - nail_shape (str): round/square/almond/coffin/stiletto/oval
        - decorations (list): 饰品列表
        - style_tags (list): 风格标签
        - style_description_en (str): 一句话英文描述（用于生图 prompt）
    """
    try:
        from deerflow.models import create_chat_model
        model = create_chat_model(thinking_enabled=False, attach_tracing=False)

        img_b64 = _encode_image(style_image_path)

        prompt = (
            "You are a nail art style analyst. Analyze this nail art image and return ONLY valid JSON:\n"
            "{\n"
            '  "colors": ["rose", "gold"],\n'
            '  "texture": "glitter",\n'
            '  "nail_shape": "almond",\n'
            '  "decorations": ["rhinestone"],\n'
            '  "style_tags": ["nail_art", "glamorous"],\n'
            '  "style_description_en": "rose gold glitter nail art with rhinestone decorations"\n'
            "}\n"
            "texture options: glitter|matte|glossy|gradient|marble|solid\n"
            "nail_shape options: round|square|almond|coffin|stiletto|oval\n"
            f"User note: {user_description or 'none'}"
        )

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
        fallback = {**_FALLBACK, "style_description_en": user_description or _FALLBACK["style_description_en"]}
        return json.dumps(fallback, ensure_ascii=False)
    except Exception as e:
        logger.warning("StyleUnderstanding fallback (LLM unavailable): %s", e)
        fallback = {**_FALLBACK, "style_description_en": user_description or _FALLBACK["style_description_en"]}
        return json.dumps(fallback, ensure_ascii=False)
