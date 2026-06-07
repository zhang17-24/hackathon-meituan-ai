"""基于多模态用户画像 + Chinese-CLIP 的款式推荐引擎。

支持:
- 向量相似度召回 (多模态 512d)
- 分维度推荐 (颜色/图案/风格)
- MMR 多样化重排
- 以图搜图 (query_image_path)
"""

import json
import logging
import os

from langchain.tools import tool

from .base import get_db, get_user_multidim_profile

logger = logging.getLogger(__name__)

_CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")


def _get_nail_styles_collection():
    import chromadb
    client = chromadb.PersistentClient(path=_CHROMA_DIR)
    return client.get_or_create_collection("nail_styles", embedding_function=None)


def _mmr_rerank(candidates: list[dict], query_vec: list[float], top_k: int, lambda_param: float = 0.7) -> list[dict]:
    """MMR (Maximal Marginal Relevance) 重排：平衡相关性和多样性。

    Args:
        candidates: [{"style_id", "description", "category", "image_path", "similarity", "_embedding"}]
        query_vec: 查询向量
        top_k: 返回数量
        lambda_param: 相关性权重 (0-1), 越大越偏相关性, 越小越偏多样性
    """
    import numpy as np

    if len(candidates) <= top_k:
        return candidates

    query = np.array(query_vec, dtype=float)
    selected = []
    remaining = list(candidates)

    for _ in range(min(top_k, len(candidates))):
        if not remaining:
            break
        scores = []
        for c in remaining:
            relevance = c.get("similarity", 0.0)
            if selected:
                # 惩罚与已选款式的相似度
                c_emb = np.array(c.get("_embedding", []), dtype=float)
                if len(c_emb) > 0:
                    max_sim = max(
                        float(np.dot(c_emb, np.array(s.get("_embedding", []), dtype=float)))
                        for s in selected
                        if len(s.get("_embedding", [])) > 0
                    )
                else:
                    max_sim = 0.0
                diversity = 1.0 - max_sim
            else:
                diversity = 1.0
            mmr_score = lambda_param * relevance + (1 - lambda_param) * diversity
            scores.append(mmr_score)

        best_idx = int(np.argmax(scores))
        selected.append(remaining.pop(best_idx))

    return selected


def _cold_start_recommend(top_k: int) -> str:
    """冷启动：返回 ops_signals 中点击量最高的款式。"""
    try:
        with get_db() as conn:
            rows = conn.execute("""
                SELECT style_id, COUNT(*) as cnt
                FROM ops_signals
                WHERE signal_type IN ('click','save','order')
                GROUP BY style_id
                ORDER BY cnt DESC
                LIMIT ?
            """, (top_k,)).fetchall()
        recs = [{"style_id": r["style_id"], "description": "热门款式", "similarity": 0.8}
                for r in rows]
        return json.dumps({
            "recommendations": recs,
            "count": len(recs),
            "message": "暂无偏好记录，推荐热门款式",
            "is_cold_start": True,
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"recommendations": [], "count": 0, "error": str(e)})


@tool
def nail_style_recommend_tool(user_id: str = "", top_k: int = 5,
                              query_mode: str = "general",
                              query_image_path: str = "",
                              query_text: str = "",
                              color_group: str = "",
                              pattern_type: str = "",
                              exclude_tried: bool = True) -> str:
    """多模态美甲款式推荐：支持画像推荐、以图搜图、文本搜索、条件过滤。

    Args:
        user_id: 用户唯一标识 (query_mode=general 时必填)。
        top_k: 返回推荐数量，默认 5。
        query_mode: "general"(基于画像推荐) | "image"(以图搜图) | "text"(文本搜索) | "diverse"(分维度多风格推荐)。
        query_image_path: query_mode=image 时用，参考图路径。
        query_text: query_mode=text 时用，中文搜索描述。
        color_group: 颜色过滤 (light/dark/warm/cool)。
        pattern_type: 图案类型过滤 (如 "cow_spots"/"french"/"gradient")。
        exclude_tried: 是否排除已试款式，默认 true。

    Returns:
        {"recommendations": [{"style_id","description","category","image_path","similarity","match_reason"}],
         "count": n, "query_mode": "...", "message": "..."}
    """
    try:
        import numpy as np

        col = _get_nail_styles_collection()
        if col.count() == 0:
            return _cold_start_recommend(top_k)

        query_vec = None

        # ── 构建查询向量 ──
        if query_mode == "image" and query_image_path:
            from .embedding import encode_query_image
            img_vec, _query_meta = encode_query_image(query_image_path)
            if img_vec is not None:
                query_vec = img_vec.tolist()
            else:
                return json.dumps({"error": "图片编码失败，请检查图片路径", "recommendations": [], "count": 0})

        elif query_mode == "text" and query_text:
            from .embedding import encode_text
            query_vec = encode_text([query_text])[0].tolist()

        elif query_mode == "diverse" and user_id:
            # 分维度多样化推荐
            profile = get_user_multidim_profile(user_id)
            if profile and profile["color_vector"]:
                query_vec = profile["color_vector"]
            elif profile:
                query_vec = profile["pref_vector"]

        else:
            # general: 基于用户画像
            if not user_id:
                return _cold_start_recommend(top_k)
            profile = get_user_multidim_profile(user_id)
            if profile is None:
                return _cold_start_recommend(top_k)
            query_vec = profile["pref_vector"]

        if query_vec is None:
            return _cold_start_recommend(top_k)

        # ── ChromaDB 向量召回 (取 top_k+15 供后续过滤和重排) ──
        n_retrieve = min(top_k + 15, col.count())

        where_filter = None
        if color_group or pattern_type:
            where_filter = {}
            if color_group:
                where_filter["color_group"] = color_group
            if pattern_type:
                where_filter["pattern_type"] = pattern_type

        results = col.query(
            query_embeddings=[query_vec],
            n_results=n_retrieve,
            include=["documents", "metadatas", "distances", "embeddings"],
            where=where_filter if where_filter else None,
        )

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]
        embs = results.get("embeddings")
        embs = embs[0] if embs else [None] * len(docs)

        # ── 排除已试款式 ──
        tried = set()
        if exclude_tried and user_id:
            with get_db() as conn:
                tried_rows = conn.execute(
                    "SELECT DISTINCT style_id FROM ops_signals WHERE user_id=? ORDER BY id DESC LIMIT 20",
                    (user_id,)
                ).fetchall()
            tried = {r["style_id"] for r in tried_rows}

        candidates = []
        for doc, meta, dist, emb in zip(docs, metas, dists, embs):
            sid = meta.get("style_id", "")
            if exclude_tried and sid in tried:
                continue
            sim = round(max(0.0, 1.0 - float(dist)), 3)
            match_reason = _generate_match_reason(meta, sim)
            candidates.append({
                "style_id": sid,
                "description": doc,
                "category": meta.get("category", ""),
                "image_path": meta.get("image_path", ""),
                "similarity": sim,
                "match_reason": match_reason,
                "_embedding": list(emb) if emb is not None else [],
            })

        # ── MMR 重排 ──
        final_recs = _mmr_rerank(candidates, query_vec, top_k)

        # 清理内部字段
        for r in final_recs:
            r.pop("_embedding", None)

        mode_desc = {"general": "画像推荐", "image": "以图搜图", "text": "文本搜索", "diverse": "多样化推荐"}
        return json.dumps({
            "recommendations": final_recs,
            "count": len(final_recs),
            "query_mode": query_mode,
            "message": f"{mode_desc.get(query_mode, query_mode)}: 为您推荐 {len(final_recs)} 款",
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("NailStyleRecommend failed: %s", e)
        return _cold_start_recommend(top_k)


def _generate_match_reason(meta: dict, similarity: float) -> str:
    """根据款式特征和相似度生成匹配理由。"""
    category = meta.get("category", "")
    color_tags = meta.get("color_tags", "")

    if similarity >= 0.92:
        level = "高度匹配"
    elif similarity >= 0.82:
        level = "较为相似"
    elif similarity >= 0.70:
        level = "风格相近"
    else:
        level = "可能感兴趣"

    parts = [level]
    if category:
        parts.append(f"{category}风格")
    if color_tags:
        parts.append(f"{color_tags}色系")
    return "，".join(parts)
