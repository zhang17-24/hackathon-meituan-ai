# backend/packages/harness/nailflow/tools/nail/hand_detect.py
"""检测手部姿态，返回指尖坐标和甲床 bounding box。

mediapipe 与主项目依赖链（kubernetes 30 要求 protobuf>=6）存在根本的
protobuf 版本冲突，无法同进程共存。检测逻辑运行在隔离的 .mp-venv 中
（见 scripts/mp_hand_detect.py），本工具通过 subprocess 调用。
"""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from langchain.tools import tool

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[5]
_MP_PYTHON = os.getenv(
    "MEDIAPIPE_PYTHON",
    str(_BACKEND_DIR / ".mp-venv" / "bin" / "python"),
)
_MP_SCRIPT = _BACKEND_DIR / "scripts" / "mp_hand_detect.py"


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
        if not _MP_SCRIPT.exists():
            return json.dumps({
                "detected": False,
                "message": f"手部检测脚本不存在（{_MP_SCRIPT}）。请检查 backend/.mp-venv 是否已初始化。",
                "nail_bboxes": [],
                "image_size": {},
            }, ensure_ascii=False)

        proc = subprocess.run(
            [str(_MP_PYTHON), str(_MP_SCRIPT), image_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            logger.error("mp_hand_detect stderr: %s", proc.stderr[-500:])
            return json.dumps({
                "detected": False,
                "message": "手部检测进程异常退出，请稍后重试",
                "nail_bboxes": [],
                "image_size": {},
            }, ensure_ascii=False)

        result = json.loads(proc.stdout.strip())
        return json.dumps(result, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({
            "detected": False,
            "message": "手部检测超时，请稍后重试",
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
