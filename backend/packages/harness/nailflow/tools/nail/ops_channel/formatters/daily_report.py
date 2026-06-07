# ops_channel/formatters/daily_report.py
"""日报格式化：趋势数据 + 运营方案 → CardMessage。"""
from __future__ import annotations
from typing import Any
from ..delivery.messages.base import CardMessage
from ..delivery.messages.card import CardButton, CardSection


def format_daily_report(trend_data: dict[str, Any], actions_data: dict[str, Any], days: int = 7) -> CardMessage:
    sections: list[CardSection] = []

    hot = trend_data.get("hot_styles", [])[:3]
    if hot:
        lines = []
        for i, s in enumerate(hot, 1):
            sid = s.get("style_id", "?")
            reason = s.get("reason", "")
            action = s.get("suggested_action", "")
            lines.append(f"{i}. {sid} — {reason} → {action}")
        sections.append(CardSection(title="📈 爆款 TOP3", lines=lines))

    cold = trend_data.get("cold_styles", [])[:2]
    if cold:
        lines = [f"· {s.get('style_id','?')} — {s.get('reason','')}" for s in cold]
        sections.append(CardSection(title="⚠️ 冷门预警", lines=lines))

    summary = trend_data.get("trend_summary", "")
    if summary:
        sections.append(CardSection(title="📊 趋势摘要", lines=[summary]))

    actions = actions_data.get("marketing_actions", [])[:2]
    if actions:
        lines = [f"· {a.get('title','')} — {a.get('reason','')} (预期: {a.get('expected_metric','')})" for a in actions]
        sections.append(CardSection(title="💡 运营建议", lines=lines))

    source = trend_data.get("data_source", f"近{days}日运营信号")
    sections.append(CardSection(title="📎 数据来源", lines=[source]))

    buttons = [
        CardButton(label="查看详情", action="view_detail", value="daily_report"),
        CardButton(label="手动刷新", action="refresh_report", value="daily_report"),
    ]

    return CardMessage(header_title=f"美甲运营日报 | {days}日趋势", header_color="pink", sections=sections, buttons=buttons)
