# backend/packages/harness/deerflow/tools/nail/nail_style_recommend.py
"""基于用户偏好向量，在款式向量空间中查找最近邻，返回推荐款式。"""
import json
import logging
import os

from langchain.tools import tool

from .base import get_db

logger = logging.getLogger(__name__)

_CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")


def _get_nail_styles_collection():
    import chromadb
    from chromadb.utils import embedding_functions
    client = chromadb.PersistentClient(path=_CHROMA_DIR)
    ef = embedding_functions.DefaultEmbeddingFunction()
    return client.get_or_create_collection("nail_styles", embedding_function=ef)


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
def nail_style_recommend_tool(user_id: str, top_k: int = 5) -> str:
    """基于用户偏好向量，推荐向量空间中最近邻的美甲款式。

    Args:
        user_id: 用户唯一标识。
        top_k: 返回推荐数量，默认 5。

    Returns:
        {"recommendations": [{"style_id","description","category","image_path","similarity"}],
         "count": n, "message": "..."}
    """
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT pref_vector FROM nail_user_prefs WHERE user_id=?", (user_id,)
            ).fetchone()

        if row is None:
            return _cold_start_recommend(top_k)

        pref_vec = json.loads(row["pref_vector"])
        col = _get_nail_styles_collection()

        if col.count() == 0:
            return _cold_start_recommend(top_k)

        results = col.query(
            query_embeddings=[pref_vec],
            n_results=min(top_k + 5, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        docs  = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        with get_db() as conn:
            tried_rows = conn.execute(
                "SELECT DISTINCT style_id FROM ops_signals WHERE user_id=? ORDER BY id DESC LIMIT 10",
                (user_id,)
            ).fetchall()
        tried = {r["style_id"] for r in tried_rows}

        recs = [
            {
                "style_id":    m.get("style_id", ""),
                "description": doc,
                "category":    m.get("category", ""),
                "image_path":  m.get("image_path", ""),
                "similarity":  round(max(0.0, 1.0 - float(d)), 3),
            }
            for doc, m, d in zip(docs, metas, dists)
            if m.get("style_id") not in tried
        ][:top_k]

        return json.dumps({
            "recommendations": recs,
            "count": len(recs),
            "message": f"基于您的偏好推荐 {len(recs)} 款",
        }, ensure_ascii=False)

    except Exception as e:
        logger.error("NailStyleRecommend failed: %s", e)
        return _cold_start_recommend(top_k)
