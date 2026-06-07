"""Rule-based answer builder and citation formatter for nail consult."""

from __future__ import annotations

from urllib.parse import urlparse


def _trim_text(text: str, limit: int = 120) -> str:
    cleaned = " ".join((text or "").replace("\n", " ").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _display_style_name(style: dict, fallback_index: int) -> str:
    style_id = str(style.get("style_id", "")).strip()
    if style_id:
        return style_id.replace("_", " ").replace("-", " ")
    category = str(style.get("category", "")).strip()
    if category:
        return category
    return f"推荐款式{fallback_index}"


def _extract_source_label(match: dict) -> str:
    title = str(match.get("title", "")).strip()
    source_url = str(match.get("source_url", "")).strip()
    if title:
        return title
    if source_url:
        host = urlparse(source_url).netloc.replace("www.", "")
        return host or source_url
    topic_id = str(match.get("topic_id", "")).strip()
    return topic_id or "知识库"


def format_citations(knowledge_results: list[dict], style_results: list[dict]) -> list[dict]:
    citations: list[dict] = []
    seen_knowledge: set[tuple[str, str]] = set()
    seen_styles: set[str] = set()

    for match in knowledge_results:
        label = _extract_source_label(match)
        source_url = str(match.get("source_url", "")).strip()
        dedupe_key = (label, source_url)
        if dedupe_key in seen_knowledge:
            continue
        seen_knowledge.add(dedupe_key)
        citations.append({
            "id": f"K{len(seen_knowledge)}",
            "type": "knowledge",
            "label": label,
            "title": str(match.get("title", "")).strip(),
            "topic_id": str(match.get("topic_id", "")).strip(),
            "url": source_url,
        })

    for style in style_results:
        style_id = str(style.get("style_id", "")).strip()
        if not style_id or style_id in seen_styles:
            continue
        seen_styles.add(style_id)
        citations.append({
            "id": f"S{len(seen_styles)}",
            "type": "style",
            "label": _display_style_name(style, len(seen_styles)),
            "style_id": style_id,
            "source": str(style.get("source", "")).strip(),
            "image_path": str(style.get("image_path", "")).strip(),
        })

    return citations


def _build_knowledge_section(knowledge_results: list[dict], citations: list[dict]) -> list[str]:
    if not knowledge_results:
        return []

    citation_lookup: dict[tuple[str, str], str] = {}
    for citation in citations:
        if citation.get("type") != "knowledge":
            continue
        key = (str(citation.get("label", "")), str(citation.get("url", "")))
        citation_lookup[key] = str(citation.get("id", ""))

    lines = ["基于检索到的专业资料，先给你结论："]
    for match in knowledge_results[:3]:
        snippet = _trim_text(str(match.get("content", "")), limit=150)
        label = _extract_source_label(match)
        key = (label, str(match.get("source_url", "")).strip())
        citation_id = citation_lookup.get(key, "")
        suffix = f" [{citation_id}]" if citation_id else ""
        lines.append(f"{len(lines)}. {snippet}{suffix}")
    return lines


def _build_style_section(style_results: list[dict]) -> list[str]:
    if not style_results:
        return []

    lines = ["可以优先参考这几款方向："]
    for idx, style in enumerate(style_results[:3], start=1):
        name = _display_style_name(style, idx)
        reason = _trim_text(str(style.get("match_reason", "")), limit=40)
        description = _trim_text(str(style.get("description", "")), limit=90)
        line = f"{idx}. {name}"
        extras: list[str] = []
        if reason:
            extras.append(reason)
        if description:
            extras.append(description)
        if extras:
            line += " - " + "；".join(extras)
        lines.append(line)
    return lines


def _build_rewrite_hint(rewrite: dict, intent: str) -> str:
    parts: list[str] = []
    pattern_type = str(rewrite.get("pattern_type", "")).strip()
    color_group = str(rewrite.get("color_group", "")).strip()
    topic = str(rewrite.get("topic", "")).strip()
    if pattern_type:
        parts.append(f"图案偏好={pattern_type}")
    if color_group:
        parts.append(f"色系偏好={color_group}")
    if topic and intent != "knowledge":
        parts.append(f"补充知识主题={topic}")
    if not parts:
        return ""
    return "我已按你的需求做结构化理解：" + "，".join(parts) + "。"


def _build_citation_lines(citations: list[dict]) -> list[str]:
    if not citations:
        return []

    lines = ["参考来源："]
    for citation in citations[:6]:
        if citation.get("type") == "knowledge":
            label = str(citation.get("label", "")).strip() or "知识库"
            url = str(citation.get("url", "")).strip()
            line = f"[{citation['id']}] {label}"
            if url:
                line += f" {url}"
            lines.append(line)
            continue

        label = str(citation.get("label", "")).strip() or str(citation.get("style_id", "")).strip()
        source = str(citation.get("source", "")).strip()
        line = f"[{citation['id']}] 款式库 {label}"
        if source:
            line += f" ({source})"
        lines.append(line)
    return lines


def build_consult_answer(
    *,
    user_query: str,
    intent: str,
    rewrite: dict,
    knowledge_results: list[dict],
    style_results: list[dict],
) -> dict:
    citations = format_citations(knowledge_results, style_results)
    lines: list[str] = []

    rewrite_hint = _build_rewrite_hint(rewrite, intent)
    if rewrite_hint:
        lines.append(rewrite_hint)

    if intent == "knowledge":
        lines.extend(_build_knowledge_section(knowledge_results, citations))
        if style_results:
            lines.extend(_build_style_section(style_results))
    else:
        if style_results:
            lines.extend(_build_style_section(style_results))
        if knowledge_results:
            lines.append("补充一个和你当前需求相关的知识点：")
            first_match = knowledge_results[0]
            lines.append(_trim_text(str(first_match.get("content", "")), limit=150))

    if not lines:
        lines.append(f"暂时没有检索到和“{user_query}”高度相关的内容，建议放宽条件后再试一次。")

    citation_lines = _build_citation_lines(citations)
    if citation_lines:
        lines.extend(citation_lines)

    return {
        "answer": "\n".join(lines),
        "citations": citations,
    }
