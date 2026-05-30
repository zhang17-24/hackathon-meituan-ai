# backend/packages/harness/deerflow/tools/nail/unified_tryon.py
"""统一试戴工具 — Seedream 多图参考模式，一步完成：款式分析 → 生图。

Agent 只需调用这一个工具：传入 手图 + 款式图，直接返回试戴效果图。
内部使用 Vision 模型分析款式 + Seedream 多图参考生图。
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

_TIMEOUT = int(os.getenv("NAIL_IMAGE_API_TIMEOUT", "60"))


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


def _resolve_style_structured(style_image_path: str) -> dict:
    """逐指分析款式：每个指甲单独识别设计，防止图案互串。"""
    from deerflow.models.router import ModelRouter, Capability
    from deerflow.models import create_chat_model
    from .base import resolve_image_path

    resolution = ModelRouter.resolve("unified_tryon_tool", Capability.VISION)
    if resolution is None:
        logger.warning("No vision model for style analysis")
        return {"style_description_en": "beautiful elegant nail art design", "nails": [], "same_on_all": True}

    resolved = resolve_image_path(style_image_path)
    img_b64 = _read_b64_data_url(str(resolved))

    prompt = (
        "Analyze EVERY individual fingernail in this nail art reference image. "
        "Look at the hand from LEFT to RIGHT: thumb, index, middle, ring, pinky.\n\n"
        "For EACH nail, report its EXACT design. Different nails may have DIFFERENT designs!\n\n"
        "Return ONLY valid JSON, no markdown:\n"
        "{\n"
        '  "same_on_all": false,\n'
        '  "nail_shape": "square / squoval",\n'
        '  "nail_length": "medium",\n'
        '  "finish": "high gloss top coat",\n'
        '  "nails": [\n'
        '    {\n'
        '      "finger": "thumb",\n'
        '      "base_color": "nude pink (hex #F5D9C3)",\n'
        '      "tip": "white french tip, ~2mm thin line",\n'
        '      "pattern": "none",\n'
        '      "full_design_en": "nude pink base with white french tip, no pattern"\n'
        '    },\n'
        '    {\n'
        '      "finger": "index",\n'
        '      "base_color": "nude pink (hex #F5D9C3)",\n'
        '      "tip": "white french tip, ~2mm thin line",\n'
        '      "pattern": "none",\n'
        '      "full_design_en": "nude pink base with white french tip, no pattern"\n'
        '    },\n'
        '    {\n'
        '      "finger": "middle",\n'
        '      "base_color": "pure white",\n'
        '      "tip": "none",\n'
        '      "pattern": "irregular black cow-print organic patches, NOT dots, unique amoeba-like contours, 3-5 patches distributed naturally",\n'
        '      "full_design_en": "white base with irregular black cow-print patches, NO french tip"\n'
        '    },\n'
        '    {\n'
        '      "finger": "ring",\n'
        '      "base_color": "pure white",\n'
        '      "tip": "none",\n'
        '      "pattern": "irregular black cow-print organic patches, NOT dots, unique amoeba-like contours, 3-5 patches distributed naturally",\n'
        '      "full_design_en": "white base with irregular black cow-print patches, NO french tip"\n'
        '    },\n'
        '    {\n'
        '      "finger": "pinky",\n'
        '      "base_color": "nude pink (hex #F5D9C3)",\n'
        '      "tip": "white french tip, ~2mm thin line",\n'
        '      "pattern": "none",\n'
        '      "full_design_en": "nude pink base with white french tip, no pattern"\n'
        '    }\n'
        '  ],\n'
        '  "style_description_zh": "一句中文描述完整款式"\n'
        "}\n\n"
        "CRITICAL RULES:\n"
        "- same_on_all: true ONLY if ALL 5 nails have IDENTICAL design. If any nail is different, set false.\n"
        "- For EACH nail, examine it individually. Do NOT assume all nails are the same.\n"
        "- pattern: if nail has NO pattern, write 'none'. If it has pattern, describe the EXACT shapes — NEVER call them 'dots' unless perfectly circular.\n"
        "- tip: if NO french tip, write 'none'.\n"
        "- full_design_en: ONE sentence per nail with COMPLETE design description.\n"
    )

    model = create_chat_model(name=resolution.name, thinking_enabled=False, attach_tracing=False)
    msg = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": img_b64}},
        {"type": "text", "text": prompt},
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
        logger.warning("Failed to parse style JSON, using raw text: %s", raw[:200])
        return {"style_description_en": raw[:500], "nails": [], "same_on_all": True}


def _get_credentials() -> tuple[str, str, str] | None:
    """Get image API credentials: env var or DB model config."""
    env_key = os.getenv("NAIL_IMAGE_API_KEY", "")
    env_url = os.getenv("NAIL_IMAGE_API_URL", "")
    if env_key and env_url:
        return env_key, env_url, os.getenv("NAIL_IMAGE_MODEL", "doubao-seedream-5-0-260128")

    from deerflow.models.router import ModelRouter, Capability
    resolution = ModelRouter.resolve("unified_tryon_tool", Capability.IMAGE_GEN)
    if resolution and resolution.api_key and resolution.api_base:
        return resolution.api_key, resolution.api_base.rstrip("/") + "/images/generations", resolution.model_id
    return None


@tool
def unified_tryon_tool(
    hand_image_path: str,
    style_image_path: str,
    user_request: str = "",
) -> str:
    """一键 AI 美甲试戴：分析款式图 → 多图参考生图 → 返回效果图。调用后即完成试戴。

    IMPORTANT: After this tool returns, reply with the image_url using markdown image syntax:
    ![试戴结果](image_url)
    Then STOP. Do NOT call any other tools.

    Args:
        hand_image_path: 用户手图文件路径。
        style_image_path: 美甲款式参考图文件路径。
        user_request: 用户额外文字要求（可选）。

    Returns:
        JSON: image_url (可直接在聊天中展示的 URL), style_zh, message, error
    """
    try:
        result_path = RESULTS_DIR / f"result_{uuid.uuid4().hex[:8]}.jpg"

        # ── Step 1: 获取凭据 ──
        creds = _get_credentials()
        if creds is None:
            from .base import resolve_image_path
            import shutil
            shutil.copy(str(resolve_image_path(hand_image_path)), str(result_path))
            return json.dumps({
                "result_path": str(result_path), "is_mock": True,
                "message": "未配置生图 API，返回原图作为 mock 结果。请在设置中为生图工具绑定模型（如 doubao-seedream-5-0）。",
                "style_zh": "",
            }, ensure_ascii=False)

        api_key, api_url, model_name = creds
        logger.info("UnifiedTryon: model_id=%s url=%s", model_name, api_url[:60])

        # ── Step 2: 逐指款式分析 ──
        logger.info("UnifiedTryon: analyzing style per-nail...")
        style = _resolve_style_structured(style_image_path)
        nails = style.get("nails", [])
        same_on_all = style.get("same_on_all", True)
        nail_shape = style.get("nail_shape", "")
        finish = style.get("finish", "high gloss")
        style_desc_zh = style.get("style_description_zh", "")
        logger.info("UnifiedTryon: %d nails, same_on_all=%s", len(nails), same_on_all)

        # ── Step 3: 构建分层 prompt ──
        hand_data_url = _read_b64_data_url(hand_image_path)
        style_data_url = _read_b64_data_url(style_image_path)

        # 层 1: 全局保留约束
        preservation = (
            "LAYER 1 - HAND PRESERVATION (highest priority): "
            "Keep image 1's hand 100% unchanged. Preserve exactly: "
            "skin tone, skin texture, finger shape, finger length, "
            "knuckle wrinkles, veins, cuticles, nail bed shape, "
            "shadows, lighting direction, background, camera angle. "
        )

        # ── style_zh 供前端展示 ──
        style_desc_zh = style.get("style_description_zh", "")
        if not style_desc_zh and nails:
            style_desc_zh = "; ".join(n.get("full_design_en", "")[:60] for n in nails)

        # ── Seedream prompt: 优先级排序(手部→逐指→权限→材质) + 图案精度补充 ──
        if not same_on_all and len(nails) == 5:
            positions = {"pinky": "far left", "ring": "left", "middle": "center",
                         "index": "right", "thumb": "far right"}

            # 图案精度补充：当 vision 模型描述太简略时，添加视觉锚点
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

            finger_parts = []
            for n in nails:
                f = n.get("finger", "?")
                pos = positions.get(f, f)
                design = n.get("full_design_en", "")
                pattern_raw = n.get("pattern", "none")

                # 补充图案精度
                if pattern_raw != "none":
                    for keyword, anchor in PATTERN_ANCHORS.items():
                        if keyword in pattern_raw.lower() and anchor not in design.lower():
                            design += f", {anchor}"

                # 补充法式边精度
                tip_raw = n.get("tip", "none")
                if tip_raw != "none" and "thin" not in tip_raw.lower():
                    if "french" in tip_raw.lower():
                        design += ", thin 2mm line only, NOT thick block"

                finger_parts.append(f"{f.upper()} ({pos}): {design}")

            per_finger_block = "; ".join(finger_parts)

            # 权限集合
            has_pattern = {n["finger"] for n in nails if n.get("pattern", "none") != "none"}
            has_tip = {n["finger"] for n in nails if n.get("tip", "none") != "none"}
            all_f = {"thumb", "index", "middle", "ring", "pinky"}
            only_p = ", ".join(f.upper() for f in sorted(has_pattern)) if has_pattern else "NONE"
            only_t = ", ".join(f.upper() for f in sorted(has_tip)) if has_tip else "NONE"
            no_p = ", ".join(f.upper() for f in sorted(all_f - has_pattern))
            no_t = ", ".join(f.upper() for f in sorted(all_f - has_tip))
            # 需要保护的手指（有独特特征的）
            vulnerable = [f.upper() for f in sorted((all_f - has_pattern) & has_tip)]
            vulnerable += [f.upper() for f in sorted((all_f - has_tip) & has_pattern)]

            prompt_text = (
                # 1. 手部保留（最前，权重最高）
                f"Keep the hand in image 1 completely unchanged: exact skin tone, wrinkles, joints, lighting, background. "
                f"Image 1 is back of hand (palm down). Image 2 is reference. Map fingers: thumb→thumb, index→index, middle→middle, ring→ring, pinky→pinky. "
                # 2. 逐指设计（核心信息，分号分隔）
                f"Apply nail art EXACTLY per finger: {per_finger_block}. "
                # 3. 强权限否定（CRITICAL RULE 前缀增强注意力）
                f"CRITICAL RULE: ONLY [{only_p}] may have black patterns. [{no_p}] must be solid color with ZERO patterns. "
                f"CRITICAL RULE: ONLY [{only_t}] may have white french tip. [{no_t}] must have NO white line at nail tip. "
                f"CRITICAL RULE: Do NOT copy any pattern from one finger to another. "
                f"CRITICAL RULE: Do NOT make all nails identical. Each finger has its OWN design. "
                + (f"CRITICAL RULE: {', '.join(vulnerable)} must keep its unique design, do NOT change it to match other fingers. " if vulnerable else "") +
                # 4. 材质（最后，即使被忽略也不影响结构）
                f"Photorealistic glossy gel polish, natural light, 4K beauty photo."
            )
        else:
            desc = nails[0].get("full_design_en", "") if nails else style.get("style_description_en", "")
            prompt_text = (
                f"Keep the hand in image 1 completely unchanged. Image 2 is nail art reference. "
                f"Apply the nail design from image 2 to ALL fingernails in image 1 identically: {desc}. "
                f"Photorealistic glossy gel polish, 4K."
            )

        payload = {
            "model": model_name,
            "prompt": prompt_text,
            "image": [hand_data_url, style_data_url],
            "sequential_image_generation": "disabled",
            "size": "2K",
            "response_format": "b64_json",
            "watermark": False,
        }

        logger.info("UnifiedTryon: calling Seedream, prompt_len=%d\nPROMPT:\n%s", len(prompt_text), prompt_text)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # ── Step 4: 解析响应 ──
        img_b64 = None
        if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
            first = data["data"][0]
            img_b64 = first.get("b64_json") or first.get("url")

        if not img_b64:
            return json.dumps({
                "error": f"Seedream 未返回图像。响应: {str(data)[:300]}",
                "result_path": "", "is_mock": False,
                "style_zh": style_desc_zh or style_desc_en,
            }, ensure_ascii=False)

        # 保存
        if img_b64.startswith("http"):
            with httpx.Client(timeout=30) as dl:
                img_data = dl.get(img_b64).content
            with open(str(result_path), "wb") as f:
                f.write(img_data)
        else:
            with open(str(result_path), "wb") as f:
                f.write(base64.b64decode(img_b64))

        image_url = f"/api/nail/image?path={result_path}"
        return json.dumps({
            "result_path": str(result_path),
            "image_url": image_url,
            "is_mock": False,
            "message": f"试戴生成成功",
            "style_zh": style_desc_zh or style_desc_en,
        }, ensure_ascii=False)

    except httpx.TimeoutException:
        return json.dumps({"error": f"生图 API 超时（>{_TIMEOUT}s）", "result_path": "", "is_mock": False}, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"Seedream HTTP {e.response.status_code}：{e.response.text[:200]}", "result_path": "", "is_mock": False}, ensure_ascii=False)
    except Exception as e:
        logger.error("UnifiedTryon failed: %s", e)
        return json.dumps({"error": f"试戴失败（{type(e).__name__}）：{e}", "result_path": "", "is_mock": False}, ensure_ascii=False)
