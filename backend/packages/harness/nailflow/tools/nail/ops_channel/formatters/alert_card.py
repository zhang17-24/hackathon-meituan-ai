# ops_channel/formatters/alert_card.py
"""告警格式化：信号突增 → CardMessage。"""
from __future__ import annotations
from ..delivery.messages.base import CardMessage
from ..delivery.messages.card import CardButton, CardSection


def format_trend_alert(style_id: str, current_count: int, baseline: float, multiplier: float, style_name: str = "") -> CardMessage:
    display_name = style_name or f"款式 {style_id}"
    sections: list[CardSection] = [
        CardSection(
            title="🚨 爆款告警",
            lines=[f"{display_name} ({style_id}) 信号异常飙升", ""],
            highlight_fields={"1小时内信号": str(current_count), "基线均值": f"{baseline:.1f}", "超出倍数": f"{multiplier:.1f}x"},
        ),
        CardSection(title="建议操作", lines=["· 核实数据真实性（排除刷量）", "· 如真实爆款 → 生成限时套餐", "· 检查库存/美甲师排期"]),
    ]
    buttons = [
        CardButton(label="查看款式", action="view_detail", value=style_id, style="primary"),
        CardButton(label="生成限时套餐", action="create_promotion", value=style_id),
        CardButton(label="忽略", action="ignore_alert", value=style_id, style="default"),
    ]
    return CardMessage(header_title=f"爆款告警: {display_name}", header_color="red", sections=sections, buttons=buttons)
