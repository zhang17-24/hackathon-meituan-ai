# backend/packages/harness/deerflow/tools/nail/nail_mask.py
"""根据甲床 bbox 列表生成甲面 mask PNG（白色=甲面，黑色=其他）。"""
import json
import logging
import uuid
from pathlib import Path

from langchain.tools import tool
from PIL import Image, ImageDraw

from .base import RESULTS_DIR

logger = logging.getLogger(__name__)


@tool
def nail_mask_tool(image_path: str, nail_bboxes_json: str) -> str:
    """根据 hand_detect_tool 的 bbox 生成甲面 mask PNG。

    Args:
        image_path: 原始手图路径（用于获取图像尺寸）。
        nail_bboxes_json: hand_detect_tool 输出的完整 JSON 字符串，
                          或仅包含 nail_bboxes 数组的 JSON 字符串。

    Returns:
        JSON 字符串，字段：
        - mask_path (str): 生成的 mask PNG 文件路径
        - nail_count (int): 检测到的指甲数量
        - image_size (dict): {"width": w, "height": h}
        - error (str): 失败时的错误信息
    """
    try:
        data = json.loads(nail_bboxes_json)

        # 兼容两种输入格式
        if isinstance(data, dict):
            bboxes = data.get("nail_bboxes", [])
            img_size = data.get("image_size")
        elif isinstance(data, list):
            bboxes = data
            img_size = None
        else:
            bboxes = []
            img_size = None

        # 获取图像尺寸
        if img_size and img_size.get("width") and img_size.get("height"):
            w, h = img_size["width"], img_size["height"]
        else:
            with Image.open(image_path) as img:
                w, h = img.size

        # 创建黑色底图，用椭圆绘制白色甲面区域
        mask = Image.new("RGB", (w, h), (0, 0, 0))
        draw = ImageDraw.Draw(mask)

        pad = 4  # 略微扩展 bbox，使甲面覆盖更完整
        for bbox in bboxes:
            x1 = max(bbox.get("x1", 0) - pad, 0)
            y1 = max(bbox.get("y1", 0) - pad, 0)
            x2 = min(bbox.get("x2", w) + pad, w)
            y2 = min(bbox.get("y2", h) + pad, h)
            draw.ellipse([x1, y1, x2, y2], fill=(255, 255, 255))

        mask_path = RESULTS_DIR / f"mask_{uuid.uuid4().hex[:8]}.png"
        mask.save(str(mask_path))

        return json.dumps({
            "mask_path": str(mask_path),
            "nail_count": len(bboxes),
            "image_size": {"width": w, "height": h},
        })

    except FileNotFoundError:
        return json.dumps({"error": f"图片文件不存在：{image_path}", "mask_path": "", "nail_count": 0})
    except Exception as e:
        logger.error("NailMask failed: %s", e)
        return json.dumps({"error": f"Mask 生成失败：{e}", "mask_path": "", "nail_count": 0})
