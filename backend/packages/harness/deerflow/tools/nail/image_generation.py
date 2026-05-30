# backend/packages/harness/deerflow/tools/nail/image_generation.py
"""调用豆包 Seedream API 进行多图参考生图美甲试戴，未配置时 mock。"""
import base64
import json
import logging
import os
import shutil
import uuid
from pathlib import Path

import httpx
from langchain.tools import tool

from .base import RESULTS_DIR

logger = logging.getLogger(__name__)

_TIMEOUT = int(os.getenv("NAIL_IMAGE_API_TIMEOUT", "60"))


def _read_b64_data_url(path: str) -> str:
    """Read image file and return data URL: data:image/<ext>;base64,<b64>"""
    from .base import resolve_image_path
    resolved = resolve_image_path(path)
    ext = Path(str(resolved)).suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
    with open(str(resolved), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


@tool
def image_generation_tool(
    hand_image_path: str,
    mask_path: str,
    prompt_json: str,
) -> str:
    """调用豆包 Seedream 多图参考生图 API，生成美甲试戴效果图。

    将手图（图1）和美甲款式参考图（图2）一起发给 Seedream，
    通过 prompt 描述替换美甲的操作，模型直接输出试戴效果图。

    Args:
        hand_image_path: 用户手图的文件路径（作为图1参考图）。
        mask_path: 甲面 mask 路径（保留参数兼容，Seedream 模式下不使用）。
        prompt_json: prompt_builder_tool 输出的 JSON，含 style_prompt_en（英文款描述）。

    Returns:
        JSON: result_path, is_mock, message, error
    """
    try:
        # 解析 prompt
        prompts = json.loads(prompt_json) if isinstance(prompt_json, str) else prompt_json
        style_desc = (
            prompts.get("style_prompt_en")
            or prompts.get("style_description_en")
            or prompts.get("style_summary_zh")
            or "beautiful nail art design"
        )

        result_path = RESULTS_DIR / f"result_{uuid.uuid4().hex[:8]}.jpg"

        # ── 凭据解析 ──
        env_key = os.getenv("NAIL_IMAGE_API_KEY", "")
        env_url = os.getenv("NAIL_IMAGE_API_URL", "")
        if env_key and env_url:
            api_key = env_key
            api_url = env_url
            model_name = os.getenv("NAIL_IMAGE_MODEL", "doubao-seedream-5-0-260128")
        else:
            from deerflow.models.router import ModelRouter, Capability
            resolution = ModelRouter.resolve("image_generation_tool", Capability.IMAGE_GEN)
            if resolution and resolution.api_key and resolution.api_base:
                api_key = resolution.api_key
                api_url = resolution.api_base.rstrip("/") + "/images/generations"
                model_name = resolution.model_id
                logger.info("ImageGeneration via Router: model=%s source=%s", model_name, resolution.source)
            else:
                logger.warning("Image API not configured — mock")
                from .base import resolve_image_path
                shutil.copy(str(resolve_image_path(hand_image_path)), str(result_path))
                return json.dumps({
                    "result_path": str(result_path), "is_mock": True,
                    "message": "未配置生图 API，返回原图作为 mock 结果。",
                }, ensure_ascii=False)

        # ── 编码两张参考图（多图生图模式）──
        hand_data_url = _read_b64_data_url(hand_image_path)

        # 尝试读取款式参考图路径（从 prompt_json 中可能包含）
        style_path = prompts.get("style_image_path", "")
        if style_path:
            try:
                style_data_url = _read_b64_data_url(style_path)
            except Exception:
                style_data_url = None
        else:
            style_data_url = None

        # ── 构建 Seedream 多图参考 payload ──
        # 图1=手图, 图2=款式参考(如果有)
        reference_images = [hand_data_url]
        if style_data_url:
            reference_images.append(style_data_url)

        # prompt: 描述替换操作
        if style_data_url:
            prompt_text = (
                f"Keep image 1's hand completely unchanged (skin tone, fingers, joints, "
                f"shadows, lighting, background). Only change the fingernail area to match "
                f"the nail art style from image 2 exactly. "
                f"Nail design: {style_desc}. "
                f"High fidelity, photorealistic, commercial beauty photo."
            )
        else:
            prompt_text = (
                f"Keep the hand completely unchanged (skin tone, fingers, joints, "
                f"shadows, lighting, background). Only change the fingernail area: "
                f"{style_desc}. "
                f"High fidelity, photorealistic, commercial beauty photo."
            )

        payload = {
            "model": model_name,
            "prompt": prompt_text,
            "image": reference_images,
            "sequential_image_generation": "disabled",
            "size": "2K",
            "response_format": "b64_json",
            "watermark": False,
        }

        logger.info("Seedream: sending %d ref images, prompt len=%d", len(reference_images), len(prompt_text))

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(api_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # ── 解析 Seedream 响应 ──
        img_b64 = None
        if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
            first = data["data"][0]
            if "b64_json" in first:
                img_b64 = first["b64_json"]
            elif "url" in first:
                img_b64 = first["url"]  # download from URL

        if not img_b64:
            # 兼容旧格式
            img_b64 = data.get("image") or data.get("output", {}).get("image", "")

        if not img_b64:
            return json.dumps({
                "error": f"API 未返回图像。响应: {str(data)[:300]}",
                "result_path": "", "is_mock": False,
            }, ensure_ascii=False)

        # 保存结果
        if img_b64.startswith("http"):
            with httpx.Client(timeout=30) as dl:
                img_data = dl.get(img_b64).content
            with open(str(result_path), "wb") as f:
                f.write(img_data)
        else:
            with open(str(result_path), "wb") as f:
                f.write(base64.b64decode(img_b64))

        return json.dumps({
            "result_path": str(result_path),
            "is_mock": False,
            "message": "试戴生成成功",
        }, ensure_ascii=False)

    except httpx.TimeoutException:
        return json.dumps({"error": f"生图 API 超时（>{_TIMEOUT}s）", "result_path": "", "is_mock": False}, ensure_ascii=False)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"生图 API HTTP {e.response.status_code}：{e.response.text[:200]}", "result_path": "", "is_mock": False}, ensure_ascii=False)
    except FileNotFoundError as e:
        return json.dumps({"error": f"输入文件不存在：{e}", "result_path": "", "is_mock": False}, ensure_ascii=False)
    except Exception as e:
        logger.error("ImageGeneration failed: %s", e)
        return json.dumps({"error": f"生图失败（{type(e).__name__}）：{e}", "result_path": "", "is_mock": False}, ensure_ascii=False)
