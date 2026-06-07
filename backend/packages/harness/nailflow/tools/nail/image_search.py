"""以图搜图工具：用户上传参考图 → 局部化美甲编码 → ChromaDB 搜索相似款式。

与 nail_style_recommend 的区别：
- nail_style_recommend: 基于用户画像的个性化推荐
- image_search: 纯基于图片视觉相似度的款式检索
"""

import json
import logging
import os

from langchain.tools import tool

from .base import get_db

logger = logging.getLogger(__name__)

_CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")


@tool
def image_search_tool(query_image_path: str, top_k: int = 10,
                      filter_category: str = "",
                      filter_color_group: str = "") -> str:
    """用参考图搜索款式库中视觉最相似的款式（以图搜图）。

    可以单独使用，也可以和 nail_style_recommend_tool 组合使用：
    先用 image_search 找到库中最相似的款式，
    再用推荐工具基于用户画像个性化排序。

    Args:
        query_image_path: 参考美甲图文件路径。
        top_k: 返回数量，默认 10。
        filter_category: 可选，限定类别（如"法式"/"渐变"/"花纹"）。
        filter_color_group: 可选，限定色系（"light"/"dark"/"warm"/"cool"）。

    Returns:
        {"matches": [{"style_id", "description", "category", "color_tags",
                       "image_path", "similarity", "match_reason"}],
         "count": n, "query_mode": "image"}
    """
    try:
        from .embedding import encode_query_image

        # Step 1: 图片编码
        img_vec, query_meta = encode_query_image(query_image_path)
        if img_vec is None:
            return json.dumps({
                "error": "图片编码失败。请确认已安装 torch/transformers。",
                "matches": [], "count": 0, "query_mode": "image",
            }, ensure_ascii=False)

        # Step 2: ChromaDB 向量检索
        import chromadb

        client = chromadb.PersistentClient(path=_CHROMA_DIR)
        col = client.get_or_create_collection("nail_styles", embedding_function=None)

        if col.count() == 0:
            return json.dumps({
                "matches": [], "count": 0, "query_mode": "image",
                "message": "款式库为空，请先导入款式数据。",
            }, ensure_ascii=False)

        where_filter = None
        if filter_category or filter_color_group:
            where_filter = {}
            if filter_category:
                where_filter["category"] = filter_category
            if filter_color_group:
                where_filter["color_group"] = filter_color_group

        n_retrieve = min(top_k + 5, col.count())
        results = col.query(
            query_embeddings=[img_vec.tolist()],
            n_results=n_retrieve,
            include=["documents", "metadatas", "distances"],
            where=where_filter if where_filter else None,
        )

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        # Step 3: 构建结果
        matches = []
        for doc, meta, dist in zip(docs, metas, dists):
            sim = round(max(0.0, 1.0 - float(dist)), 3)
            category = meta.get("category", "")
            color_tags = meta.get("color_tags", "")

            if sim >= 0.90:
                reason = "视觉高度匹配"
            elif sim >= 0.80:
                reason = "视觉相似度高"
            elif sim >= 0.65:
                reason = "有相似元素"
            else:
                reason = "风格相近"

            if category:
                reason += f"，同属{category}类"
            if color_tags:
                reason += f"，{color_tags}色系"

            matches.append({
                "style_id": meta.get("style_id", ""),
                "description": doc,
                "category": category,
                "color_tags": color_tags,
                "image_path": meta.get("image_path", ""),
                "similarity": sim,
                "match_reason": reason,
            })

        # 按相似度降序
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        matches = matches[:top_k]

        return json.dumps({
            "matches": matches,
            "count": len(matches),
            "query_mode": "image",
            "query_embedding": query_meta,
            "message": f"以图搜图完成，找到 {len(matches)} 个视觉相似款式",
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("ImageSearch failed: %s", e)
        return json.dumps({
            "error": f"以图搜图失败: {e}",
            "matches": [], "count": 0, "query_mode": "image",
        }, ensure_ascii=False)
