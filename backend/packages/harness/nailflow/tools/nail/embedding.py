"""多模态嵌入模块：Chinese-CLIP 图文共享向量空间 (512d)。

相比直接对整张手图做编码，这里增加了美甲专用的视觉预处理策略：
- 优先使用 hand_detect 的甲面 bbox 做局部裁剪
- 生成弱化背景/手部纹理的 masked view
- 多视角（单指甲 + 局部手部）聚合，降低手势和背景噪声
"""

import json
import logging
import os
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_NAME = os.getenv("NAIL_EMBEDDING_MODEL", "OFA-Sys/chinese-clip-vit-base-patch16")
_DEVICE = os.getenv("NAIL_EMBEDDING_DEVICE", "cpu")
_DIM = 512
_MODEL = None
_PROCESSOR = None


def _ensure_model():
    """延迟加载 Chinese-CLIP 模型（首次调用时加载）。"""
    global _MODEL, _PROCESSOR
    if _MODEL is not None:
        return True

    try:
        import torch
        from transformers import ChineseCLIPModel, ChineseCLIPProcessor

        logger.info("Loading Chinese-CLIP model: %s (device=%s)", _MODEL_NAME, _DEVICE)
        _MODEL = ChineseCLIPModel.from_pretrained(_MODEL_NAME)
        _PROCESSOR = ChineseCLIPProcessor.from_pretrained(_MODEL_NAME)
        _MODEL.eval()
        if _DEVICE != "cpu" and torch.cuda.is_available():
            _MODEL = _MODEL.to(_DEVICE)
        logger.info("Chinese-CLIP loaded — %d dim", _MODEL.config.projection_dim)
        return True
    except ImportError:
        logger.warning("Chinese-CLIP deps not installed (torch/transformers)")
        return False
    except Exception as e:
        logger.warning("Failed to load Chinese-CLIP: %s", e)
        return False


def _extract_feature_tensor(output):
    if hasattr(output, "pooler_output"):
        return output.pooler_output
    return output


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return vec.astype(np.float32)


def _normalize_rows(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (vecs / norms).astype(np.float32)


def encode_text(texts: list[str]) -> np.ndarray:
    """将中文文本列表编码为归一化向量 [N, 512]。"""
    if not _ensure_model():
        return _fallback_encode(texts)

    import torch

    try:
        with torch.no_grad():
            inputs = _PROCESSOR(text=texts, return_tensors="pt", padding=True)
            if _DEVICE != "cpu" and torch.cuda.is_available():
                inputs = {k: v.to(_DEVICE) for k, v in inputs.items()}
            features = _extract_feature_tensor(_MODEL.get_text_features(**inputs))
            features = torch.nn.functional.normalize(features, dim=1)
            return features.cpu().numpy().astype(np.float32)
    except Exception as e:
        logger.warning("Chinese-CLIP text encode failed, fallback: %s", e)
        return _fallback_encode(texts)


def _load_resolved_image(image_path: str):
    from PIL import Image

    from .base import resolve_image_path

    resolved = resolve_image_path(image_path)
    return Image.open(resolved).convert("RGB")


def _run_hand_detect(image_path: str) -> dict[str, Any] | None:
    """尽量复用 hand_detect_tool，失败时返回 None。"""
    try:
        from .hand_detect import hand_detect_tool

        for caller in (
            lambda: hand_detect_tool.invoke({"image_path": image_path}),
            lambda: hand_detect_tool.func(image_path),
            lambda: hand_detect_tool.run(image_path),
        ):
            try:
                raw = caller()
                if isinstance(raw, str):
                    return json.loads(raw)
                if isinstance(raw, dict):
                    return raw
            except Exception:
                continue
    except Exception as e:
        logger.debug("hand_detect unavailable for embedding: %s", e)
    return None


def _sanitize_nail_bboxes(raw_bboxes: list[dict] | None, width: int, height: int) -> list[dict]:
    valid: list[dict] = []
    for bbox in raw_bboxes or []:
        try:
            x1 = max(0, min(int(bbox.get("x1", 0)), width))
            y1 = max(0, min(int(bbox.get("y1", 0)), height))
            x2 = max(0, min(int(bbox.get("x2", 0)), width))
            y2 = max(0, min(int(bbox.get("y2", 0)), height))
        except (TypeError, ValueError):
            continue
        if x2 - x1 < 8 or y2 - y1 < 8:
            continue
        area = (x2 - x1) * (y2 - y1)
        valid.append({
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "center_x": (x1 + x2) / 2,
            "center_y": (y1 + y2) / 2,
            "area": area,
        })

    if len(valid) <= 5:
        return sorted(valid, key=lambda item: (item["center_y"], item["center_x"]))

    # 优先保留面积最大的 5 个甲面，避免双手入镜时把远处小手指带进来。
    valid.sort(key=lambda item: item["area"], reverse=True)
    valid = valid[:5]
    return sorted(valid, key=lambda item: (item["center_y"], item["center_x"]))


def _expand_bbox(bbox: dict, width: int, height: int, scale_x: float = 1.25, scale_y: float = 1.35) -> tuple[int, int, int, int]:
    cx = (bbox["x1"] + bbox["x2"]) / 2
    cy = (bbox["y1"] + bbox["y2"]) / 2
    bw = max(8.0, (bbox["x2"] - bbox["x1"]) * scale_x)
    bh = max(8.0, (bbox["y2"] - bbox["y1"]) * scale_y)
    x1 = max(0, int(round(cx - bw / 2)))
    y1 = max(0, int(round(cy - bh / 2)))
    x2 = min(width, int(round(cx + bw / 2)))
    y2 = min(height, int(round(cy + bh / 2)))
    return x1, y1, x2, y2


def _union_bbox(bboxes: list[dict], width: int, height: int, margin_ratio: float = 0.18) -> tuple[int, int, int, int]:
    x1 = min(b["x1"] for b in bboxes)
    y1 = min(b["y1"] for b in bboxes)
    x2 = max(b["x2"] for b in bboxes)
    y2 = max(b["y2"] for b in bboxes)
    bw = x2 - x1
    bh = y2 - y1
    mx = max(12, int(bw * margin_ratio))
    my = max(12, int(bh * margin_ratio))
    return max(0, x1 - mx), max(0, y1 - my), min(width, x2 + mx), min(height, y2 + my)


def _build_masked_focus_image(image, bboxes: list[dict]):
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    width, height = image.size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for bbox in bboxes:
        draw.ellipse(_expand_bbox(bbox, width, height, scale_x=1.5, scale_y=1.6), fill=255)
    mask = mask.filter(ImageFilter.MaxFilter(17))
    mask = mask.filter(ImageFilter.GaussianBlur(8))

    blurred_bg = image.filter(ImageFilter.GaussianBlur(18))
    subdued_bg = ImageEnhance.Color(blurred_bg).enhance(0.2)
    neutral_bg = ImageEnhance.Contrast(subdued_bg).enhance(0.9)
    return Image.composite(image, neutral_bg, mask)


def _prepare_image_views(image_path: str, prefer_localized: bool = True) -> tuple[list[Any], dict[str, Any]]:
    image = _load_resolved_image(image_path)
    width, height = image.size
    metadata: dict[str, Any] = {"strategy": "full_image", "nail_count": 0, "used_hand_detect": False}

    if not prefer_localized:
        return [image], metadata

    detection = _run_hand_detect(image_path)
    bboxes = _sanitize_nail_bboxes((detection or {}).get("nail_bboxes"), width, height)
    if not bboxes:
        return [image], metadata

    metadata = {"strategy": "localized_nails", "nail_count": len(bboxes), "used_hand_detect": True}
    views = []
    masked = _build_masked_focus_image(image, bboxes)
    ux1, uy1, ux2, uy2 = _union_bbox(bboxes, width, height)
    views.append(masked.crop((ux1, uy1, ux2, uy2)))
    for bbox in bboxes:
        x1, y1, x2, y2 = _expand_bbox(bbox, width, height)
        views.append(image.crop((x1, y1, x2, y2)))
    return views, metadata


def _aggregate_vectors(vectors: list[np.ndarray], drop_outlier: bool = True) -> np.ndarray | None:
    if not vectors:
        return None

    arr = np.array(vectors, dtype=np.float32)
    arr = _normalize_rows(arr)

    if drop_outlier and arr.shape[0] >= 4:
        centroid = _normalize(np.mean(arr, axis=0))
        sims = arr @ centroid
        keep_count = max(3, arr.shape[0] - 1)
        keep_idx = np.argsort(sims)[-keep_count:]
        arr = arr[keep_idx]

    return _normalize(np.mean(arr, axis=0))


def _encode_pil_images(images: list[Any]) -> np.ndarray | None:
    if not images:
        return None
    if not _ensure_model():
        return None

    import torch

    try:
        with torch.no_grad():
            inputs = _PROCESSOR(images=images, return_tensors="pt")
            if _DEVICE != "cpu" and torch.cuda.is_available():
                inputs = {k: v.to(_DEVICE) for k, v in inputs.items()}
            features = _extract_feature_tensor(_MODEL.get_image_features(**inputs))
            features = torch.nn.functional.normalize(features, dim=1)
            return features.cpu().numpy().astype(np.float32)
    except Exception as e:
        logger.warning("Chinese-CLIP PIL image encode failed: %s", e)
        return None


def encode_query_image(image_path: str, text_hint: str = "") -> tuple[np.ndarray | None, dict[str, Any]]:
    """查询侧图像编码，优先使用甲面局部视图并可选融合文本提示。"""
    try:
        views, metadata = _prepare_image_views(image_path, prefer_localized=True)
        view_vectors = _encode_pil_images(views)
        if view_vectors is None or len(view_vectors) == 0:
            return None, {"strategy": "failed", "nail_count": 0, "used_hand_detect": False}

        context_vec = np.array(view_vectors[0], dtype=np.float32)
        nail_vecs = [np.array(v, dtype=np.float32) for v in view_vectors[1:]]
        local_vec = _aggregate_vectors(nail_vecs) if nail_vecs else None

        parts = []
        if local_vec is not None:
            parts.append(local_vec * 0.75)
            parts.append(context_vec * 0.20)
        else:
            parts.append(context_vec * 0.95)

        if text_hint:
            text_vec = encode_text([text_hint])[0]
            parts.append(text_vec * 0.05)

        final_vec = _normalize(np.sum(parts, axis=0))
        metadata["view_count"] = len(views)
        return final_vec, metadata
    except Exception as e:
        logger.warning("encode_query_image failed for %s: %s", image_path, e)
        return None, {"strategy": "failed", "nail_count": 0, "used_hand_detect": False}


def encode_image(image_path: str) -> np.ndarray | None:
    """将图片编码为归一化向量 [512]。

    默认走美甲专用局部化编码，失败时降级为整图编码。
    """
    vec, _meta = encode_query_image(image_path)
    if vec is not None:
        return vec

    if not _ensure_model():
        return None

    try:
        full_image = _load_resolved_image(image_path)
        features = _encode_pil_images([full_image])
        if features is None or len(features) == 0:
            return None
        return np.array(features[0], dtype=np.float32)
    except Exception as e:
        logger.warning("Chinese-CLIP image encode failed for %s: %s", image_path, e)
        return None


def encode_images(image_paths: list[str]) -> np.ndarray | None:
    """批量图片编码 -> [N, 512]。"""
    vectors = []
    for path in image_paths:
        vec = encode_image(path)
        if vec is None:
            return None
        vectors.append(vec)
    if not vectors:
        return None
    return np.array(vectors, dtype=np.float32)


def fused_style_embedding(
    image_path: str | None = None,
    text_desc: str | None = None,
    color_hex: str | None = None,
    weights: tuple[float, float, float] = (0.7, 0.25, 0.05),
) -> np.ndarray | None:
    """生成款式的融合向量：视觉 + 语义 + 颜色锚点。"""
    vectors = []
    w_img, w_txt, w_clr = weights

    if image_path is not None:
        img_vec = encode_image(image_path)
        if img_vec is not None:
            vectors.append(img_vec * w_img)

    if text_desc is not None:
        txt_vec = encode_text([text_desc])[0]
        vectors.append(txt_vec * w_txt)

    if color_hex is not None and w_clr > 0:
        color_vec = _hex_to_color_vector(color_hex)
        if color_vec is not None:
            vectors.append(color_vec * w_clr)

    if not vectors:
        return None

    return _normalize(np.sum(vectors, axis=0))


def _hex_to_color_vector(hex_color: str) -> np.ndarray | None:
    """将 hex 颜色映射到 CLIP 嵌入空间中的颜色锚点。

    用预定义的颜色锚点文本编码，然后在锚点中做插值。
    512d 空间太大，直接映射到前几个 PCA 维度不现实。
    这里用颜色描述文本的嵌入作为近似。
    """
    try:
        color_names = _hex_to_color_name(hex_color)
        return encode_text([color_names])[0]
    except Exception as e:
        logger.debug("color vector encoding failed: %s", e)
        return None


def _hex_to_color_name(hex_color: str) -> str:
    """hex → 中文颜色描述。"""
    hex_color = hex_color.lstrip("#").upper()
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

    brightness = (max(r, g, b) + min(r, g, b)) / 2

    if brightness < 60:
        return "深色调美甲"
    elif brightness > 200:
        return "浅白亮色美甲"
    elif r > 200 and g > 180 and b > 180:
        return "裸粉肤色美甲"
    elif r > 200 and g < 100 and b < 100:
        return "正红色美甲"
    elif r > 200 and g < 100 and b > 150:
        return "玫粉色美甲"
    elif b > 200 and g > 180:
        return "蓝紫色调美甲"
    elif r < 100 and g < 100 and b > 180:
        return "深邃蓝色美甲"
    elif g > 180 and r < 100:
        return "绿色调美甲"
    elif r > 180 and g > 150 and b < 100:
        return "金色美甲"
    return "彩色美甲"


class NailStyleEmbeddingFunction:
    """ChromaDB 兼容的文字嵌入函数。用于 collection 文档嵌入。"""

    def name(self) -> str:
        return "chinese-clip-vit-base-patch16"

    def __call__(self, input: list[str]) -> list[list[float]]:
        """ChromaDB EmbeddingFunction 接口。"""
        embeddings = encode_text(input)
        return embeddings.tolist()


def _fallback_encode(texts: list[str]) -> np.ndarray:
    """降级到 ChromaDB 内置的 all-MiniLM-L6-v2 (384d → pad to 512d)。"""
    from chromadb.utils import embedding_functions

    logger.warning("Using fallback embedding (all-MiniLM-L6-v2, 384d padded to 512d)")
    ef = embedding_functions.DefaultEmbeddingFunction()
    embeddings_384 = np.array(ef(texts), dtype=np.float32)
    embeddings_512 = np.zeros((embeddings_384.shape[0], _DIM), dtype=np.float32)
    embeddings_512[:, :384] = embeddings_384
    for i in range(embeddings_512.shape[0]):
        norm = np.linalg.norm(embeddings_512[i])
        if norm > 0:
            embeddings_512[i] /= norm
    return embeddings_512


def get_embedding_function():
    """获取 ChromaDB collection 使用的嵌入函数。"""
    return NailStyleEmbeddingFunction()


def get_embedding_dim() -> int:
    return _DIM
