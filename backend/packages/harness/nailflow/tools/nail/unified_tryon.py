# backend/packages/harness/nailflow/tools/nail/unified_tryon.py
"""统一试戴工具 — Seedream/万相 多图参考模式，一步完成：款式分析 → 生图。

Agent 只需调用这一个工具：传入 手图 + 款式图，直接返回试戴效果图。
内部使用 Vision 模型分析款式 + 多图参考生图。
"""
import base64
import json
import logging
import os
import uuid
from pathlib import Path

import httpx
from langchain.tools import tool
from langchain_core.messages import HumanMessage

from .base import RESULTS_DIR

logger = logging.getLogger(__name__)

_TIMEOUT = int(os.getenv("NAIL_IMAGE_API_TIMEOUT", "240"))


def _emit_progress(stage: str, progress: int, message: str = "") -> None:
    """向 SSE 流发送试戴进度事件（stream_mode=custom 时前端可接收）。"""
    try:
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
        writer({
            "type": "nail_tryon_progress",
            "stage": stage,
            "progress": progress,
            "message": message,
        })
    except Exception:
        pass


def _detect_image_format(data: bytes) -> str:
    """通过 magic bytes 检测图片格式，返回扩展名 (jpg/png/webp/bmp)。"""
    if data[:4] == b"\x89PNG":
        return "png"
    if data[:2] == b"\xff\xd8":
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:2] == b"BM":
        return "bmp"
    return "jpg"


def _read_b64_data_url(path: str) -> str:
    """Read image file, return data:image/<ext>;base64,<b64>"""
    from .base import resolve_image_path
    resolved = resolve_image_path(path)
    ext = Path(str(resolved)).suffix.lower().lstrip(".")
    mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "bmp": "bmp"}
    mime = mime_map.get(ext, "jpeg")
    with open(str(resolved), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


# ── 款式分析 ─────────────────────────────────────────────────


def _resolve_style_structured(style_image_path: str) -> dict:
    """逐指分析款式：每个指甲单独识别设计，防止图案互串。

    当 VLM 首次返回空结果时，用简化 prompt 重试一次作为降级。
    """
    from nailflow.models.router import ModelRouter, Capability
    from nailflow.models import create_chat_model
    from .base import resolve_image_path

    resolution = ModelRouter.resolve("unified_tryon_tool", Capability.VISION)
    if resolution is None:
        logger.warning("No vision model for style analysis")
        return _fallback_style()

    resolved = resolve_image_path(style_image_path)
    img_b64 = _read_b64_data_url(str(resolved))

    prompt = (
        "你是一位专业的美甲款式分析师。这张图片是一张美甲款式参考图。\n\n"
        "请仔细观察每根手指的指甲设计，从左到右依次为：拇指(thumb)、食指(index)、"
        "中指(middle)、无名指(ring)、小指(pinky)。\n\n"
        "重要提示：这是一张美甲款式图，指甲上一定有颜色或设计（纯色/法式/渐变/图案/饰品等）。"
        "请精确描述你实际看到的设计。不要输出[裸甲]或[未涂指甲油]等描述。\n\n"
        "返回纯 JSON（不要 markdown 代码块）：\n"
        "{\n"
        '  "same_on_all": true,\n'
        '  "nail_shape": "square",\n'
        '  "nail_length": "medium",\n'
        '  "finish": "high gloss top coat",\n'
        '  "nails": [\n'
        '    {"finger": "thumb","base_color": "nude pink","tip": "white french tip 2mm line","pattern": "none","full_design_en": "nude pink base with white french tip, no pattern"},\n'
        '    ...\n'
        '  ],\n'
        '  "style_description_zh": "裸粉色底色配白色法式边",\n'
        '  "style_description_en": "nude pink base with white french tips"\n'
        "}\n\n"
        "CRITICAL RULES:\n"
        "- 这张图一定包含美甲设计。请仔细辨认底色、纹理、图案，即使看起来比较素雅。\n"
        "- same_on_all: 仅当所有5指完全相同时才为 true。有跳指设计时为 false。\n"
        "- pattern: 无图案写 \"none\"，有图案则精确描述形状。\n"
        "- tip: 无法式边写 \"none\"。\n"
        "- full_design_en: 每指一句完整的英文设计描述。\n"
        "- 必须填写全部5根手指(thumb,index,middle,ring,pinky)。\n"
    )

    def _call_vlm(p: str) -> dict | None:
        model = create_chat_model(name=resolution.name, thinking_enabled=False, attach_tracing=False)
        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": img_b64}},
            {"type": "text", "text": p},
        ])
        resp = model.invoke([msg])
        raw = resp.content.strip()
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            return json.loads(raw.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse style JSON: %s", raw[:200])
            return None

    result = _call_vlm(prompt)

    # 降级重试：简化为整体描述
    if result and (not result.get("nails") or _is_bare_nail_result(result)):
        logger.warning("VLM returned bare-nail or empty result, retrying with simpler prompt")
        fallback_prompt = (
            "这张图片是美甲款式参考图。请分析图中的美甲设计，返回纯 JSON：\n"
            "{\n"
            '  "same_on_all": true,\n'
            '  "nail_shape": "square",\n'
            '  "nail_length": "medium",\n'
            '  "finish": "high gloss top coat",\n'
            '  "nails": [\n'
            '    {"finger":"thumb","base_color":"","tip":"none","pattern":"none","full_design_en":""},\n'
            '    {"finger":"index","base_color":"","tip":"none","pattern":"none","full_design_en":""},\n'
            '    {"finger":"middle","base_color":"","tip":"none","pattern":"none","full_design_en":""},\n'
            '    {"finger":"ring","base_color":"","tip":"none","pattern":"none","full_design_en":""},\n'
            '    {"finger":"pinky","base_color":"","tip":"none","pattern":"none","full_design_en":""}\n'
            '  ],\n'
            '  "style_description_zh": "用一句中文描述整体款式",\n'
            '  "style_description_en": "one English sentence describing the overall nail design"\n'
            "}\n\n"
            "RULES:\n"
            "- 这张图上一定是有美甲的。请观察指甲的颜色、纹理、图案、饰品、法式边等。\n"
            "- 每指必须填写，5根手指都要有。\n"
            "- full_design_en用英文描述，style_description_zh用中文描述。\n"
        )
        retry = _call_vlm(fallback_prompt)
        if retry and retry.get("nails") and not _is_bare_nail_result(retry):
            result = retry

    if result is None:
        return _fallback_style()

    return result


def _is_bare_nail_result(result: dict) -> bool:
    """检测 VLM 是否误判为裸甲。"""
    zh = (result.get("style_description_zh") or "").lower()
    en = (result.get("style_description_en") or "").lower()
    bare_keywords = ["裸甲", "未涂", "bare nail", "unpainted", "no polish", "no nail polish", "natural nail"]
    for kw in bare_keywords:
        if kw in zh or kw in en:
            return True
    nails = result.get("nails") or []
    if nails:
        all_bare = all(
            (n.get("pattern") in ("none", "", None))
            and (n.get("tip") in ("none", "", None))
            and (not (n.get("base_color") or "").strip())
            for n in nails
        )
        if all_bare:
            return True
    return False


def _fallback_style() -> dict:
    return {
        "same_on_all": True,
        "nail_shape": "square",
        "nail_length": "medium",
        "finish": "high gloss top coat",
        "nails": [],
        "style_description_en": "elegant glossy nail art with refined color",
        "style_description_zh": "精致美甲设计",
    }


# ── API 调用 ─────────────────────────────────────────────────


def _get_credentials() -> tuple[str, str, str, str] | None:
    """Get image API credentials from env var or DB model config.

    Returns (api_key, api_url, model_name, api_type).
    api_url is the FULL endpoint from api_base — no URL splicing.
    api_type is detected from the URL domain: "wan" (阿里百炼) | "seedream" (火山引擎).
    """
    env_key = os.getenv("NAIL_IMAGE_API_KEY", "")
    env_url = os.getenv("NAIL_IMAGE_API_URL", "")
    if env_key and env_url:
        api_type = "wan" if "dashscope" in env_url else "seedream"
        return env_key, env_url, os.getenv("NAIL_IMAGE_MODEL", "doubao-seedream-5-0-260128"), api_type

    from nailflow.models.router import ModelRouter, Capability
    resolution = ModelRouter.resolve("unified_tryon_tool", Capability.IMAGE_GEN)
    if resolution and resolution.api_key and resolution.api_base:
        api_base = resolution.api_base.rstrip("/")
        api_type = "wan" if "dashscope" in api_base else "seedream"
        if api_type == "wan":
            api_url = api_base
        elif api_base.endswith("/images/generations"):
            api_url = api_base
        else:
            api_url = api_base + "/images/generations"
        return resolution.api_key, api_url, resolution.model_id, api_type
    return None


def _call_wan_api(api_key: str, api_url: str, model_name: str,
                  hand_data_url: str, style_data_url: str,
                  prompt_text: str, timeout: int) -> dict:
    """Call 阿里百炼 multimodal-generation API (万相2.7 等)."""
    payload = {
        "model": model_name,
        "input": {
            "messages": [{
                "role": "user",
                "content": [
                    {"image": hand_data_url},
                    {"image": style_data_url},
                    {"text": prompt_text},
                ]
            }]
        },
        "parameters": {"size": "2K", "n": 1, "watermark": False},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(api_url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _parse_wan_response(data: dict) -> str | None:
    """Extract image URL from 万相 response. Returns URL string or None."""
    choices = data.get("output", {}).get("choices", [])
    if choices:
        for item in choices[0].get("message", {}).get("content", []):
            if item.get("type") == "image":
                return item.get("image")
    return None


# ── 主工具 ───────────────────────────────────────────────────


@tool
def unified_tryon_tool(
    hand_image_path: str,
    style_image_path: str,
    user_request: str = "",
) -> str:
    """一键 AI 美甲试戴：分析款式图 → 多图参考生图 → 返回效果图。调用后即完成试戴。

    IMPORTANT: After this tool returns, reply with the image_url using markdown image syntax:
    ![试戴结果](image_url)
    The image_url is a RELATIVE path (e.g. /api/nail/image?path=...). Use it EXACTLY as returned —
    do NOT prepend any domain or convert it to an absolute URL. Then STOP. Do NOT call any other tools.

    Args:
        hand_image_path: 用户手图文件路径。
        style_image_path: 美甲款式参考图文件路径。
        user_request: 用户额外文字要求（可选）。

    Returns:
        JSON: image_url (可直接在聊天中展示的 URL), style_zh, message, error
    """
    try:
        result_id = uuid.uuid4().hex[:8]

        # ── Step 1: 获取凭据 ──
        creds = _get_credentials()
        if creds is None:
            from .base import resolve_image_path
            import shutil
            mock_path = RESULTS_DIR / f"result_{result_id}.jpg"
            shutil.copy(str(resolve_image_path(hand_image_path)), str(mock_path))
            return json.dumps({
                "result_path": str(mock_path), "is_mock": True,
                "message": "未配置生图 API，返回原图作为 mock 结果。请在设置中为生图工具绑定模型（如 doubao-seedream-5-0）。",
                "style_zh": "",
            }, ensure_ascii=False)

        api_key, api_url, model_name, api_type = creds
        logger.info("UnifiedTryon: model_id=%s type=%s", model_name, api_type)

        _emit_progress("style", 20, "分析美甲款式...")

        # ── Step 2: 逐指款式分析 ──
        logger.info("UnifiedTryon: analyzing style per-nail...")
        style = _resolve_style_structured(style_image_path)
        nails = style.get("nails", [])
        same_on_all = style.get("same_on_all", True)
        logger.info("UnifiedTryon: %d nails, same_on_all=%s", len(nails), same_on_all)

        # ── Step 3: 构建分层 prompt ──
        hand_data_url = _read_b64_data_url(hand_image_path)
        style_data_url = _read_b64_data_url(style_image_path)

        style_desc_zh = style.get("style_description_zh", "")
        if not style_desc_zh and nails:
            style_desc_zh = "; ".join(n.get("full_design_en", "")[:60] for n in nails)

        # 图案精度补充
        PATTERN_ANCHORS = {
            "cow": "irregular organic black blotches like Holstein cow hide, NOT polka dots, NOT round spots",
            "dot": "precise small round dots, evenly spaced",
            "stripe": "thin clean parallel lines, 1mm width each",
            "marble": "natural stone veins with organic branching patterns",
            "glitter": "fine sparkling particles with random light reflections",
            "gradient": "smooth color transition, no hard edges",
            "floral": "delicate hand-painted flower petals with visible brush texture",
            "french": "thin 2mm white curved line at free edge only, NOT thick block, NOT gradient band",
        }

        if not same_on_all and len(nails) == 5:
            positions = {"pinky": "far left", "ring": "left", "middle": "center",
                         "index": "right", "thumb": "far right"}

            finger_parts = []
            for n in nails:
                f = n.get("finger", "?")
                pos = positions.get(f, f)
                design = n.get("full_design_en", "")
                pattern_raw = n.get("pattern", "none")

                if pattern_raw != "none":
                    for keyword, anchor in PATTERN_ANCHORS.items():
                        if keyword in pattern_raw.lower() and anchor not in design.lower():
                            design += f", {anchor}"

                tip_raw = n.get("tip", "none")
                if tip_raw != "none" and "thin" not in tip_raw.lower():
                    if "french" in tip_raw.lower():
                        design += ", thin 2mm line only, NOT thick block"

                finger_parts.append(f"{f.upper()} ({pos}): {design}")

            per_finger_block = "; ".join(finger_parts)

            has_pattern = {n["finger"] for n in nails if n.get("pattern", "none") != "none"}
            has_tip = {n["finger"] for n in nails if n.get("tip", "none") != "none"}
            all_f = {"thumb", "index", "middle", "ring", "pinky"}
            only_p = ", ".join(f.upper() for f in sorted(has_pattern)) if has_pattern else "NONE"
            only_t = ", ".join(f.upper() for f in sorted(has_tip)) if has_tip else "NONE"
            no_p = ", ".join(f.upper() for f in sorted(all_f - has_pattern))
            no_t = ", ".join(f.upper() for f in sorted(all_f - has_tip))
            vulnerable = [f.upper() for f in sorted((all_f - has_pattern) & has_tip)]
            vulnerable += [f.upper() for f in sorted((all_f - has_tip) & has_pattern)]

            prompt_text = (
                f"Keep the hand in image 1 completely unchanged: exact skin tone, wrinkles, joints, lighting, background. "
                f"Image 1 is back of hand (palm down). Image 2 is reference. Map fingers: thumb→thumb, index→index, middle→middle, ring→ring, pinky→pinky. "
                f"Apply nail art EXACTLY per finger: {per_finger_block}. "
                f"CRITICAL RULE: ONLY [{only_p}] may have patterns. [{no_p}] must be solid color with ZERO patterns. "
                f"CRITICAL RULE: ONLY [{only_t}] may have white french tip. [{no_t}] must have NO white line at nail tip. "
                f"CRITICAL RULE: Do NOT copy any pattern from one finger to another. "
                f"CRITICAL RULE: Do NOT make all nails identical. Each finger has its OWN design. "
                + (f"CRITICAL RULE: {', '.join(vulnerable)} must keep its unique design, do NOT change it to match other fingers. " if vulnerable else "") +
                f"Photorealistic glossy gel polish, natural light, 4K beauty photo."
            )
        else:
            desc = nails[0].get("full_design_en", "") if nails else style.get("style_description_en", "")
            prompt_text = (
                f"Keep the hand in image 1 completely unchanged. Image 2 is nail art reference. "
                f"Apply the nail design from image 2 to ALL fingernails in image 1 identically: {desc}. "
                f"Photorealistic glossy gel polish, 4K."
            )

        use_wan = (api_type == "wan")
        _emit_progress("generating", 40, "AI 正在生成试戴效果图，约需 1-2 分钟...")
        logger.info("UnifiedTryon: calling %s, prompt_len=%d",
                     "Wan2.7" if use_wan else "Seedream", len(prompt_text))

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        if use_wan:
            # ── 万相2.7 API ──
            data = _call_wan_api(api_key, api_url, model_name,
                                 hand_data_url, style_data_url,
                                 prompt_text, _TIMEOUT)
            img_b64 = _parse_wan_response(data)
        else:
            # ── Seedream API ──
            payload = {
                "model": model_name,
                "prompt": prompt_text,
                "image": [hand_data_url, style_data_url],
                "size": "2k",
                "response_format": "b64_json",
                "watermark": False,
            }
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            img_b64 = None
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                first = data["data"][0]
                img_b64 = first.get("b64_json") or first.get("url")

        if not img_b64:
            api_label = "Wan2.7" if use_wan else "Seedream"
            return json.dumps({
                "error": f"{api_label} 未返回图像。响应: {str(data)[:300]}",
                "result_path": "", "is_mock": False,
                "style_zh": style_desc_zh or "",
            }, ensure_ascii=False)

        # 下载/解码图片数据
        if img_b64.startswith("http"):
            with httpx.Client(timeout=30) as dl:
                img_data = dl.get(img_b64).content
        else:
            img_data = base64.b64decode(img_b64)

        # 检测实际图片格式
        ext = _detect_image_format(img_data)
        result_path = RESULTS_DIR / f"result_{result_id}.{ext}"

        with open(str(result_path), "wb") as f:
            f.write(img_data)

        _emit_progress("done", 100, "试戴效果生成完成")
        image_url = f"/api/nail/image?path={result_path}"
        return json.dumps({
            "result_path": str(result_path),
            "image_url": image_url,
            "is_mock": False,
            "message": "试戴生成成功",
            "style_zh": style_desc_zh or "",
        }, ensure_ascii=False)

    except httpx.TimeoutException:
        return json.dumps({"error": f"生图 API 超时（>{_TIMEOUT}s）", "result_path": "", "is_mock": False}, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"生图 API HTTP {e.response.status_code}：{e.response.text[:200]}", "result_path": "", "is_mock": False}, ensure_ascii=False)
    except Exception as e:
        logger.error("UnifiedTryon failed: %s", e)
        return json.dumps({"error": f"试戴失败（{type(e).__name__}）：{e}", "result_path": "", "is_mock": False}, ensure_ascii=False)
