# backend/packages/harness/deerflow/tools/nail/hand_detect.py
"""检测手部姿态，返回指尖坐标和甲床 bounding box。"""
import base64
import io
import json
import logging
import os
from pathlib import Path

import mediapipe as mp
import numpy as np
from langchain.tools import tool
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image

logger = logging.getLogger(__name__)

# mediapipe 0.10+ Tasks API
_BaseOptions = mp_python.BaseOptions
_HandLandmarker = mp_vision.HandLandmarker
_HandLandmarkerOptions = mp_vision.HandLandmarkerOptions
_VisionRunningMode = mp_vision.RunningMode

# 默认模型路径（从环境变量读取，或使用相对于本文件的路径）
_DEFAULT_MODEL_PATH = os.getenv(
    "MEDIAPIPE_HAND_MODEL",
    str(Path(__file__).resolve().parents[5] / "data" / "hand_landmarker.task"),
)

# 指尖 landmark ID（拇指~小指）
FINGERTIP_IDS = [4, 8, 12, 16, 20]
# 指关节 landmark ID（指甲床对应的近端）
KNUCKLE_IDS   = [3, 7, 11, 15, 19]


def _load_image(image_path: str) -> tuple[np.ndarray, mp.Image]:
    """加载图片：支持本地文件路径或 base64 字符串。

    Returns:
        (rgb_array, mp_image) 元组
    Raises:
        FileNotFoundError: 当路径不存在且不像 base64 字符串时
    """
    p = Path(image_path)
    if p.exists():
        img = Image.open(p).convert("RGB")
    elif len(image_path) > 260 or "/" not in image_path and "\\" not in image_path and not image_path.endswith(
        (".jpg", ".jpeg", ".png", ".bmp", ".webp")
    ):
        # 看起来像 base64 字符串，尝试解码
        data = base64.b64decode(image_path)
        img = Image.open(io.BytesIO(data)).convert("RGB")
    else:
        raise FileNotFoundError(f"图片文件不存在：{image_path}")
    arr = np.array(img)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)
    return arr, mp_img


@tool
def hand_detect_tool(image_path: str) -> str:
    """检测手图中的手部姿态，返回指尖坐标和甲床候选 bbox。

    Args:
        image_path: 手图的本地文件路径（绝对或相对）或 base64 字符串。

    Returns:
        JSON 字符串，字段：
        - detected (bool): 是否检测到手部
        - message (str): 检测失败时的中文提示（引导用户重拍）
        - nail_bboxes (list): 每根手指的甲床 bbox [x1,y1,x2,y2]
        - image_size (dict): {"width": w, "height": h}
    """
    try:
        img_array, mp_img = _load_image(image_path)
        h, w = img_array.shape[:2]

        model_path = _DEFAULT_MODEL_PATH
        if not Path(model_path).exists():
            return json.dumps({
                "detected": False,
                "message": (
                    f"MediaPipe 手部模型文件不存在（{model_path}）。"
                    "请下载 hand_landmarker.task 并设置环境变量 MEDIAPIPE_HAND_MODEL。"
                ),
                "nail_bboxes": [],
                "image_size": {"width": w, "height": h},
            }, ensure_ascii=False)

        options = _HandLandmarkerOptions(
            base_options=_BaseOptions(model_asset_path=model_path),
            running_mode=_VisionRunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        with _HandLandmarker.create_from_options(options) as landmarker:
            result = landmarker.detect(mp_img)

        if not result.hand_landmarks:
            return json.dumps({
                "detected": False,
                "message": (
                    "未检测到手部。建议：① 正面拍摄手背 ② 确保光线充足 "
                    "③ 手指展开、完整入镜 ④ 避免背景颜色与肤色相近"
                ),
                "nail_bboxes": [],
                "image_size": {"width": w, "height": h},
            }, ensure_ascii=False)

        nail_bboxes = []
        for hand_lm in result.hand_landmarks:
            lms = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lm]
            for tip_id, knuckle_id in zip(FINGERTIP_IDS, KNUCKLE_IDS):
                tx, ty = lms[tip_id]
                kx, ky = lms[knuckle_id]
                # 甲面宽度取指尖-关节距离的 80%，高度取 50%
                nail_w = max(int(abs(tx - kx) * 0.8), 18)
                nail_h = max(int(abs(ty - ky) * 0.5), 12)
                x1 = max(tx - nail_w // 2, 0)
                y1 = max(min(ty, ky) - nail_h // 4, 0)
                x2 = min(tx + nail_w // 2, w)
                y2 = min(max(ty, ky) + nail_h // 4, h)
                nail_bboxes.append({
                    "finger_id": tip_id,
                    "x1": x1, "y1": y1,
                    "x2": x2, "y2": y2,
                    "center_x": tx, "center_y": ty,
                })

        return json.dumps({
            "detected": True,
            "message": f"检测到 {len(result.hand_landmarks)} 只手，{len(nail_bboxes)} 个甲面区域",
            "nail_bboxes": nail_bboxes,
            "image_size": {"width": w, "height": h},
        }, ensure_ascii=False)

    except FileNotFoundError:
        return json.dumps({
            "detected": False,
            "message": f"图片文件不存在：{image_path}",
            "nail_bboxes": [],
            "image_size": {},
        }, ensure_ascii=False)
    except Exception as e:
        logger.error("HandDetect failed: %s", e)
        return json.dumps({
            "detected": False,
            "message": f"手部检测失败（{type(e).__name__}），请检查图片格式或重新拍摄",
            "nail_bboxes": [],
            "image_size": {},
        }, ensure_ascii=False)
