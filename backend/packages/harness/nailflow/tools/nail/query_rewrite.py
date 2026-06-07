"""规则版 Query Rewrite：将自然语言查询改写为结构化检索条件。"""

import json
from collections import OrderedDict

from langchain.tools import tool


_PATTERN_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("french", ("法式", "法式边", "法式款")),
    ("gradient", ("渐变", "晕染", "ombre")),
    ("floral", ("花", "碎花", "花朵", "花卉")),
    ("leopard", ("豹纹", "动物纹", "animal print")),
    ("cow", ("奶牛纹", "奶牛", "cow")),
    ("stripe", ("条纹", "斑马纹", "几何线", "线条")),
    ("plaid", ("棋盘格", "格纹", "格子")),
    ("cat_eye", ("猫眼",)),
    ("marble", ("大理石", "石纹")),
    ("glitter", ("亮片", "闪粉", "闪片", "细闪")),
    ("solid", ("纯色", "单色")),
    ("jelly", ("果冻", "玻璃", "透感", "清透")),
]

_COLOR_GROUP_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("light", ("显手白", "奶白", "裸粉", "透白", "白色", "浅色", "清透")),
    ("dark", ("深色", "暗黑", "酒红", "黑色", "深蓝", "墨绿")),
    ("warm", ("暖色", "红色", "橘色", "金色", "豆沙", "奶茶")),
    ("cool", ("冷色", "蓝色", "银色", "紫色", "灰色", "冰透")),
]

_TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("product_layers_and_finish", ("底胶", "封层", "色胶", "质感", "磨砂", "镜面", "猫眼", "果冻")),
    ("nail_shapes", ("甲型", "方圆", "方形", "圆形", "椭圆", "杏仁", "芭蕾")),
    ("biohazard_disinfection", ("消毒", "感染", "卫生", "伤口", "出血", "真菌", "细菌")),
    ("salon_safety_chemicals", ("化学", "通风", "刺激", "甲油胶", "sds", "口罩", "甲醛", "甲苯")),
    ("nail_anatomy_and_prep", ("前处理", "角质层", "甲板", "甲床", "泡水", "抛磨")),
    ("dataset_schema_recommendation", ("标签", "schema", "元数据", "检索", "rag")),
]

_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("try_on", ("试戴", "上手看看", "给我做一个", "生成效果")),
    ("knowledge", ("为什么", "怎么", "区别", "步骤", "安全吗", "能不能", "是否", "是什么")),
    ("style_search", ("找款式", "想要", "有没有", "推荐一些", "搜一下")),
]


def rewrite_query_text(query_text: str) -> dict:
    text = (query_text or "").strip()
    lower = text.lower()

    keywords: list[str] = []
    pattern_type = ""
    color_group = ""
    topic = ""
    intent = "style_search"

    for candidate_intent, hints in _INTENT_KEYWORDS:
        if any(hint in text for hint in hints):
            intent = candidate_intent
            break

    for candidate_pattern, hints in _PATTERN_KEYWORDS:
        if any(hint.lower() in lower for hint in hints):
            pattern_type = candidate_pattern
            keywords.extend(hints[:1])
            break

    for candidate_group, hints in _COLOR_GROUP_KEYWORDS:
        if any(hint in text for hint in hints):
            color_group = candidate_group
            keywords.extend(hints[:1])
            break

    for candidate_topic, hints in _TOPIC_KEYWORDS:
        if any(hint.lower() in lower for hint in hints):
            topic = candidate_topic
            if intent == "style_search":
                intent = "knowledge"
            keywords.extend(hints[:1])
            break

    rewrite_parts = [text]
    if pattern_type:
        rewrite_parts.append(f"图案类型 {pattern_type}")
    if color_group:
        rewrite_parts.append(f"综合色系 {color_group}")

    if "通勤" in text:
        rewrite_parts.append("适合通勤、低复杂度、日常简约")
        keywords.append("通勤")
    if "不要太夸张" in text or "不夸张" in text:
        rewrite_parts.append("风格简约、装饰少、不过度夸张")
        keywords.append("不夸张")
    if "短甲" in text:
        rewrite_parts.append("适合短甲、自然甲面")
        keywords.append("短甲")

    unique_keywords = list(OrderedDict.fromkeys([kw for kw in keywords if kw]))
    return {
        "intent": intent,
        "rewritten_query": "；".join(rewrite_parts),
        "pattern_type": pattern_type,
        "color_group": color_group,
        "topic": topic,
        "keywords": unique_keywords,
    }


@tool
def query_rewrite_tool(query_text: str) -> str:
    """规则版 Query Rewrite：提取意图和结构化检索条件。"""
    return json.dumps(rewrite_query_text(query_text), ensure_ascii=False)
