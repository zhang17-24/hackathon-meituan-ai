"""知识库检索工具：查询美甲知识向量库，返回最相关的知识 chunks。"""

import json
import logging
import os

from langchain.tools import tool

logger = logging.getLogger(__name__)

_CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")


def _get_nail_knowledge_collection():
    import chromadb

    client = chromadb.PersistentClient(path=_CHROMA_DIR)
    return client.get_or_create_collection("nail_knowledge", embedding_function=None)


def _infer_topic_filter(query_text: str) -> str:
    text = query_text.lower()
    if any(keyword in text for keyword in ("底胶", "封层", "质感", "磨砂", "镜面", "猫眼", "果冻")):
        return "product_layers_and_finish"
    if any(keyword in text for keyword in ("甲型", "方圆", "方形", "圆形", "椭圆", "杏仁", "芭蕾")):
        return "nail_shapes"
    if any(keyword in text for keyword in ("消毒", "感染", "卫生", "出血", "伤口", "epa")):
        return "biohazard_disinfection"
    if any(keyword in text for keyword in ("化学", "通风", "甲油胶", "甲油", "刺激", "sds", "口罩")):
        return "salon_safety_chemicals"
    if any(keyword in text for keyword in ("前处理", "角质层", "抛磨", "泡水", "甲板", "甲床")):
        return "nail_anatomy_and_prep"
    if any(keyword in text for keyword in ("标签", "元数据", "schema", "检索", "rag")):
        return "dataset_schema_recommendation"
    return ""


@tool
def knowledge_retrieval_tool(query_text: str, top_k: int = 5, topic_filter: str = "") -> str:
    """检索美甲专业知识库，返回最相关的知识片段。

    Args:
        query_text: 用户查询，例如“底胶和封层有什么区别”。
        top_k: 返回条数，默认 5。
        topic_filter: 可选，限定 topic_id，例如 "nail_shapes"。

    Returns:
        {"matches": [{"chunk_id", "topic_id", "title", "content", "similarity",
                       "tags", "source_url", "chunk_type"}],
         "count": n, "query_mode": "knowledge"}
    """
    query_text = (query_text or "").strip()
    if not query_text:
        return json.dumps({
            "matches": [],
            "count": 0,
            "query_mode": "knowledge",
            "error": "query_text 不能为空",
        }, ensure_ascii=False)

    try:
        from .embedding import encode_text

        col = _get_nail_knowledge_collection()
        if col.count() == 0:
            return json.dumps({
                "matches": [],
                "count": 0,
                "query_mode": "knowledge",
                "message": "知识库为空，请先运行导入脚本。",
            }, ensure_ascii=False)

        query_vec = encode_text([query_text])[0].tolist()
        resolved_topic = topic_filter or _infer_topic_filter(query_text)
        where = {"topic_id": resolved_topic} if resolved_topic else None

        results = col.query(
            query_embeddings=[query_vec],
            n_results=min(max(top_k, 1), col.count()),
            include=["documents", "metadatas", "distances"],
            where=where,
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        matches = []
        for doc, meta, dist in zip(docs, metas, dists):
            similarity = round(max(0.0, 1.0 - float(dist)), 3)
            raw_tags = meta.get("tags", "")
            if isinstance(raw_tags, str):
                tags = [tag for tag in raw_tags.split(",") if tag]
            else:
                tags = raw_tags or []

            matches.append({
                "chunk_id": meta.get("chunk_id", ""),
                "topic_id": meta.get("topic_id", ""),
                "title": meta.get("title", ""),
                "content": doc,
                "similarity": similarity,
                "tags": tags,
                "source_url": meta.get("source_url", ""),
                "chunk_type": meta.get("chunk_type", ""),
            })

        return json.dumps({
            "matches": matches,
            "count": len(matches),
            "query_mode": "knowledge",
            "resolved_topic": resolved_topic,
            "message": f"找到 {len(matches)} 条相关知识片段",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error("KnowledgeRetrieval failed: %s", e)
        return json.dumps({
            "matches": [],
            "count": 0,
            "query_mode": "knowledge",
            "error": f"知识检索失败: {e}",
        }, ensure_ascii=False)
