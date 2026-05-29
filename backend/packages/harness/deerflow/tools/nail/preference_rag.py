# backend/packages/harness/deerflow/tools/nail/preference_rag.py
"""用户偏好 RAG：基于 ChromaDB 存储和检索用户喜好款式，提供个性化推荐。"""
import json
import logging
import os
from typing import Optional

from langchain.tools import tool

logger = logging.getLogger(__name__)

_CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
_client: Optional[object] = None
_collection: Optional[object] = None


def _get_collection():
    """获取或初始化 ChromaDB collection（懒加载，进程内复用）。"""
    global _client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        _client = chromadb.PersistentClient(path=_CHROMA_DIR)
        ef = embedding_functions.DefaultEmbeddingFunction()
        _collection = _client.get_or_create_collection(
            name="user_preferences",
            embedding_function=ef,
        )
        return _collection
    except ImportError:
        logger.error("chromadb not installed. Run: pip install chromadb")
        raise
    except Exception as e:
        logger.error("ChromaDB init failed: %s", e)
        raise


@tool
def preference_rag_tool(action: str, user_id: str, data: str = "") -> str:
    """管理用户偏好 RAG：保存试戴偏好或查询个性化推荐。

    Args:
        action: "save"（保存用户喜好）或 "query"（查询推荐）。
        user_id: 当前用户的唯一标识。
        data: action=save 时为款式信息 JSON 字符串；
              action=query 时为查询关键词字符串。

    Returns:
        action=save: {"saved": true, "doc_id": "..."}
        action=query: {"recommendations": [...], "count": n, "message": "..."}
        失败时: {"error": "..."}
    """
    try:
        col = _get_collection()

        if action == "save":
            style_data = json.loads(data) if (data and data.strip().startswith("{")) else {"description": data}
            description = style_data.get("style_description_en") or style_data.get("description") or str(style_data)

            # 用户偏好 ID：user_id + 时间戳哈希
            import time
            doc_id = f"{user_id}_{int(time.time())}"

            meta = {"user_id": user_id}
            # 只存储字符串类型的 metadata（ChromaDB 限制）
            for k, v in style_data.items():
                if isinstance(v, str):
                    meta[k] = v
                elif isinstance(v, list):
                    meta[k] = ",".join(str(i) for i in v)

            col.add(
                documents=[description],
                metadatas=[meta],
                ids=[doc_id],
            )
            return json.dumps({"saved": True, "doc_id": doc_id}, ensure_ascii=False)

        elif action == "query":
            query_text = data or "美甲推荐"
            total = col.count()
            if total == 0:
                return json.dumps({
                    "recommendations": [],
                    "count": 0,
                    "message": "暂无偏好记录，请先试戴几款，系统会学习您的喜好",
                }, ensure_ascii=False)

            results = col.query(
                query_texts=[query_text],
                n_results=min(5, total),
                where={"user_id": user_id} if total > 0 else None,
            )
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]

            recs = []
            for doc, meta in zip(docs, metas):
                recs.append({"description": doc, "style_info": meta})

            return json.dumps({
                "recommendations": recs,
                "count": len(recs),
                "message": f"基于您的历史偏好推荐 {len(recs)} 款",
            }, ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知 action：{action}，请使用 save 或 query"})

    except Exception as e:
        logger.error("PreferenceRAG error (action=%s): %s", action, e)
        if action == "query":
            return json.dumps({
                "recommendations": [],
                "count": 0,
                "message": f"偏好查询暂不可用（{type(e).__name__}），推荐热门款式",
                "error": str(e),
            }, ensure_ascii=False)
        return json.dumps({"error": str(e), "saved": False})
