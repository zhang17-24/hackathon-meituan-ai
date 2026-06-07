# backend/packages/harness/nailflow/tools/nail/image_generation.py
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
    """调用 Seedream / 万相 多图参考生图 API，生成美甲试戴效果图。

    将手图（图1）和美甲款式参考图（图2）一起发给生图模型，
    通过 prompt 描述替换美甲的操作，模型直接输出试戴效果图。

    Args:
        hand_image_path: 用户手图的文件路径（作为图1参考图）。
        mask_path: 甲面 mask 路径（保留参数兼容，当前不使用）。
        prompt_json: prompt_builder_tool 输出的 JSON，含 style_summary_zh。

    Returns:
        JSON: result_path, image_url, is_mock, message, error
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

        result_id = uuid.uuid4().hex[:8]

        # ── 凭据解析 ──
        env_key = os.getenv("NAIL_IMAGE_API_KEY", "")
        env_url = os.getenv("NAIL_IMAGE_API_URL", "")
        if env_key and env_url:
            api_key = env_key
            api_url = env_url
            model_name = os.getenv("NAIL_IMAGE_MODEL", "doubao-seedream-5-0-260128")
            api_type = "wan" if "dashscope" in env_url else "seedream"
        else:
            from nailflow.models.router import ModelRouter, Capability
            resolution = ModelRouter.resolve("image_generation_tool", Capability.IMAGE_GEN)
            if resolution and resolution.api_key and resolution.api_base:
                api_key = resolution.api_key
                api_base = resolution.api_base.rstrip("/")
                model_name = resolution.model_id
                api_type = "wan" if "dashscope" in api_base else "seedream"
                if api_type == "wan":
                    api_url = api_base
                elif api_base.endswith("/images/generations"):
                    api_url = api_base
                else:
                    api_url = api_base + "/images/generations"
                logger.info("ImageGeneration via Router: model=%s type=%s source=%s", model_name, api_type, resolution.source)
            else:
                logger.warning("Image API not configured — mock")
                from .base import resolve_image_path
                mock_path = RESULTS_DIR / f"result_{result_id}.jpg"
                shutil.copy(str(resolve_image_path(hand_image_path)), str(mock_path))
                return json.dumps({
                    "result_path": str(mock_path), "is_mock": True,
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

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        use_wan = (api_type == "wan")
        logger.info("%s: sending %d ref images, prompt len=%d",
                     "Wan2.7" if use_wan else "Seedream", len(reference_images), len(prompt_text))

        if use_wan:
            # ── 万相2.7 API ──
            payload = {
                "model": model_name,
                "input": {
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"image": hand_data_url},
                            *([{"image": style_data_url}] if style_data_url else []),
                            {"text": prompt_text},
                        ]
                    }]
                },
                "parameters": {"size": "2K", "n": 1, "watermark": False},
            }
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # 解析万相响应
            img_url = None
            choices = data.get("output", {}).get("choices", [])
            if choices:
                for item in choices[0].get("message", {}).get("content", []):
                    if item.get("type") == "image":
                        img_url = item.get("image")
                        break
            img_b64 = img_url
        else:
            # ── Seedream API ──
            payload = {
                "model": model_name,
                "prompt": prompt_text,
                "image": reference_images,
                "sequential_image_generation": "disabled",
                "size": "2K",
                "response_format": "b64_json",
                "watermark": False,
            }
            with httpx.Client(timeout=_TIMEOUT) as client:
                resp = client.post(api_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            # 解析 Seedream 响应
            img_b64 = None
            if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
                first = data["data"][0]
                img_b64 = first.get("b64_json") or first.get("url")

            if not img_b64:
                img_b64 = data.get("image") or data.get("output", {}).get("image", "")

        if not img_b64:
            api_label = "Wan2.7" if use_wan else "Seedream"
            return json.dumps({
                "error": f"{api_label} 未返回图像。响应: {str(data)[:300]}",
                "result_path": "", "is_mock": False,
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

        image_url = f"/api/nail/image?path={result_path}"
        return json.dumps({
            "result_path": str(result_path),
            "image_url": image_url,
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
