# backend/packages/harness/deerflow/tools/nail/image_generation.py
"""调用字节生图 API 进行 inpaint 美甲试戴，未配置时 mock 返回原图。"""
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

_API_KEY = os.getenv("NAIL_IMAGE_API_KEY", "")
_API_URL = os.getenv("NAIL_IMAGE_API_URL", "")
_TIMEOUT = int(os.getenv("NAIL_IMAGE_API_TIMEOUT", "60"))


def _read_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@tool
def image_generation_tool(
    hand_image_path: str,
    mask_path: str,
    prompt_json: str,
) -> str:
    """调用字节生图 inpaint API，在甲面 mask 区域生成试戴效果图。

    Args:
        hand_image_path: 原始手图的本地路径。
        mask_path: 甲面 mask PNG 路径（白色=编辑区域）。
        prompt_json: prompt_builder_tool 返回的 JSON 字符串，含 positive_prompt/negative_prompt。

    Returns:
        JSON 字符串，字段：
        - result_path (str): 生成结果图的本地路径
        - is_mock (bool): 是否为 mock 结果
        - message (str): 说明信息
        - error (str): 失败时的错误信息
    """
    try:
        prompts = json.loads(prompt_json)
        positive = prompts.get("positive_prompt", "beautiful nail art")
        negative = prompts.get("negative_prompt", "")

        result_path = RESULTS_DIR / f"result_{uuid.uuid4().hex[:8]}.jpg"

        # 未配置 API → mock 模式（复制原图）
        if not _API_KEY or not _API_URL:
            logger.warning("Image API not configured — returning mock result (original image)")
            shutil.copy(hand_image_path, str(result_path))
            return json.dumps({
                "result_path": str(result_path),
                "is_mock": True,
                "message": "未配置生图 API，返回原图作为 mock 结果。请配置 NAIL_IMAGE_API_KEY 和 NAIL_IMAGE_API_URL。",
            })

        hand_b64 = _read_b64(hand_image_path)
        mask_b64 = _read_b64(mask_path)

        payload = {
            "model": "seedream-inpaint",
            "image": hand_b64,
            "mask": mask_b64,
            "prompt": positive,
            "negative_prompt": negative,
            "strength": 0.85,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
            "seed": 42,
        }

        headers = {
            "Authorization": f"Bearer {_API_KEY}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # 解析响应（兼容多种字段名）
        img_b64 = (
            data.get("image")
            or data.get("data", {}).get("image", "")
            or data.get("output", {}).get("image", "")
        )
        if not img_b64:
            return json.dumps({"error": f"API 未返回图像字段，响应预览：{str(data)[:200]}", "result_path": "", "is_mock": False})

        with open(str(result_path), "wb") as f:
            f.write(base64.b64decode(img_b64))

        return json.dumps({
            "result_path": str(result_path),
            "is_mock": False,
            "message": "试戴图生成成功",
        })

    except httpx.TimeoutException:
        return json.dumps({
            "error": f"生图 API 超时（>{_TIMEOUT}s）。建议降低 num_inference_steps 或重试。",
            "result_path": "",
            "is_mock": False,
        })
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "error": f"生图 API HTTP 错误 {e.response.status_code}：{e.response.text[:200]}",
            "result_path": "",
            "is_mock": False,
        })
    except FileNotFoundError as e:
        return json.dumps({"error": f"输入文件不存在：{e}", "result_path": "", "is_mock": False})
    except Exception as e:
        logger.error("ImageGeneration failed: %s", e)
        return json.dumps({"error": f"生图失败（{type(e).__name__}）：{e}", "result_path": "", "is_mock": False})
