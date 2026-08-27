"""独立环境手部检测脚本（mediapipe 隔离进程入口）。

主项目依赖链锁定 protobuf>=6（kubernetes 30 等），与 mediapipe 所需的
protobuf<=4 根本冲突，无法同进程共存。本脚本运行在独立的 .mp-venv
中，由 hand_detect_tool 通过 subprocess 调用，返回与工具一致的 JSON。

用法: .mp-venv/bin/python scripts/mp_hand_detect.py <image_path|base64>
"""
import base64
import io
import json
import os
import sys
from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image

_BaseOptions = mp_python.BaseOptions
_HandLandmarker = mp_vision.HandLandmarker
_HandLandmarkerOptions = mp_vision.HandLandmarkerOptions
_VisionRunningMode = mp_vision.RunningMode

_DEFAULT_MODEL_PATH = os.getenv(
    "MEDIAPIPE_HAND_MODEL",
    str(Path(__file__).resolve().parents[1] / "data" / "hand_landmarker.task"),
)

FINGERTIP_IDS = [4, 8, 12, 16, 20]
KNUCKLE_IDS = [3, 7, 11, 15, 19]


def _load_image(image_path: str) -> tuple[np.ndarray, mp.Image]:
    p = Path(image_path)
    if p.exists():
        img = Image.open(p).convert("RGB")
    elif not image_path.endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
        img = Image.open(io.BytesIO(base64.b64decode(image_path))).convert("RGB")
    else:
        raise FileNotFoundError(f"图片文件不存在：{image_path}")
    arr = np.array(img)
    return arr, mp.Image(image_format=mp.ImageFormat.SRGB, data=arr)


def detect(image_path: str) -> dict:
    try:
        img_array, mp_img = _load_image(image_path)
        h, w = img_array.shape[:2]

        model_path = _DEFAULT_MODEL_PATH
        if not Path(model_path).exists():
            return {
                "detected": False,
                "message": f"MediaPipe 手部模型文件不存在（{model_path}）。请下载 hand_landmarker.task。",
                "nail_bboxes": [],
                "image_size": {"width": w, "height": h},
            }

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
            return {
                "detected": False,
                "message": (
                    "未检测到手部。建议：① 正面拍摄手背 ② 确保光线充足 "
                    "③ 手指展开、完整入镜 ④ 避免背景颜色与肤色相近"
                ),
                "nail_bboxes": [],
                "image_size": {"width": w, "height": h},
            }

        nail_bboxes = []
        for hand_lm in result.hand_landmarks:
            lms = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lm]
            for tip_id, knuckle_id in zip(FINGERTIP_IDS, KNUCKLE_IDS):
                tx, ty = lms[tip_id]
                kx, ky = lms[knuckle_id]
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

        return {
            "detected": True,
            "message": f"检测到 {len(result.hand_landmarks)} 只手，{len(nail_bboxes)} 个甲面区域",
            "nail_bboxes": nail_bboxes,
            "image_size": {"width": w, "height": h},
        }
    except FileNotFoundError as e:
        return {"detected": False, "message": str(e), "nail_bboxes": [], "image_size": {}}
    except Exception as e:
        return {
            "detected": False,
            "message": f"手部检测失败（{type(e).__name__}），请检查图片格式或重新拍摄",
            "nail_bboxes": [],
            "image_size": {},
        }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"detected": False, "message": "缺少 image_path 参数", "nail_bboxes": [], "image_size": {}}))
        sys.exit(0)
    print(json.dumps(detect(sys.argv[1]), ensure_ascii=False))
