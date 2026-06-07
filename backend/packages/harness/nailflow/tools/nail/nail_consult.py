"""统一美甲咨询工具：根据用户问题自动路由到知识检索或款式推荐。"""

import json
import logging

from langchain.tools import tool

from .context_builder import build_consult_answer
from .knowledge_retrieval import knowledge_retrieval_tool
from .nail_style_recommend import nail_style_recommend_tool
from .query_rewrite import rewrite_query_text

logger = logging.getLogger(__name__)


def _safe_json_loads(payload: str) -> dict:
    try:
        return json.loads(payload)
    except Exception:
        return {}


@tool
def nail_consult_tool(user_query: str, user_id: str = "", top_k: int = 5) -> str:
    """统一美甲咨询入口：自动识别知识问答、款式搜索和试戴相关问题。

    Args:
        user_query: 用户原始问题，例如“底胶和封层有什么区别”或“通勤法式显手白”。
        user_id: 可选，若提供可用于推荐链透传用户身份。
        top_k: 返回的知识片段或推荐款式数量。

    Returns:
        JSON，包含 query_rewrite、intent、knowledge_results、style_results、answer、citations 等统一字段。
    """
    query = (user_query or "").strip()
    if not query:
        return json.dumps({
            "intent": "",
            "query_rewrite": {},
            "knowledge_results": [],
            "style_results": [],
            "answer": "user_query 不能为空",
            "citations": [],
            "message": "user_query 不能为空",
        }, ensure_ascii=False)

    try:
        rewrite = rewrite_query_text(query)
        intent = rewrite.get("intent", "style_search")
        topic = rewrite.get("topic", "")
        color_group = rewrite.get("color_group", "")
        pattern_type = rewrite.get("pattern_type", "")

        knowledge_payload: dict = {"matches": [], "count": 0}
        style_payload: dict = {"recommendations": [], "count": 0}

        # 知识型问题优先查知识库；若包含明显风格约束，再补充款式参考。
        if intent == "knowledge":
            knowledge_payload = _safe_json_loads(
                knowledge_retrieval_tool.func(query_text=query, top_k=top_k, topic_filter=topic)
            )
            if color_group or pattern_type:
                style_payload = _safe_json_loads(
                    nail_style_recommend_tool.func(
                        user_id=user_id,
                        query_mode="text",
                        query_text=query,
                        top_k=min(3, top_k),
                        color_group=color_group,
                        pattern_type=pattern_type,
                    )
                )
        else:
            # 款式搜索：优先用用户偏好向量做个性化推荐，无偏好时降级为文本搜索
            if user_id:
                style_payload = _safe_json_loads(
                    nail_style_recommend_tool.func(
                        user_id=user_id,
                        query_mode="general",
                        top_k=top_k,
                        color_group=color_group,
                        pattern_type=pattern_type,
                    )
                )
                if style_payload.get("is_cold_start"):
                    style_payload = _safe_json_loads(
                        nail_style_recommend_tool.func(
                            user_id=user_id,
                            query_mode="text",
                            query_text=query,
                            top_k=top_k,
                            color_group=color_group,
                            pattern_type=pattern_type,
                        )
                    )
            else:
                style_payload = _safe_json_loads(
                    nail_style_recommend_tool.func(
                        user_id=user_id,
                        query_mode="text",
                        query_text=query,
                        top_k=top_k,
                        color_group=color_group,
                        pattern_type=pattern_type,
                    )
                )
            if topic:
                knowledge_payload = _safe_json_loads(
                    knowledge_retrieval_tool.func(query_text=query, top_k=min(3, top_k), topic_filter=topic)
                )

        message = "已完成美甲咨询路由"
        if intent == "knowledge":
            message = f"知识问答路由完成，返回 {knowledge_payload.get('count', 0)} 条知识片段"
        elif intent in ("style_search", "try_on"):
            message = f"款式咨询路由完成，返回 {style_payload.get('count', 0)} 条推荐"

        answer_payload = build_consult_answer(
            user_query=query,
            intent=intent,
            rewrite=rewrite,
            knowledge_results=knowledge_payload.get("matches", []),
            style_results=style_payload.get("recommendations", []),
        )

        return json.dumps({
            "intent": intent,
            "query_rewrite": rewrite,
            "knowledge_results": knowledge_payload.get("matches", []),
            "style_results": style_payload.get("recommendations", []),
            "knowledge_count": knowledge_payload.get("count", 0),
            "style_count": style_payload.get("count", 0),
            "answer": answer_payload.get("answer", ""),
            "citations": answer_payload.get("citations", []),
            "message": message,
        }, ensure_ascii=False)
    except Exception as e:
        logger.error("NailConsult failed: %s", e)
        return json.dumps({
            "intent": "",
            "query_rewrite": {},
            "knowledge_results": [],
            "style_results": [],
            "answer": "",
            "citations": [],
            "error": f"咨询路由失败: {e}",
        }, ensure_ascii=False)
