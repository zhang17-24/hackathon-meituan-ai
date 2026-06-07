# ops_channel/formatters/pdf_report/builder.py
"""ReportLab PDF 拼装：Platypus 流式排版，自动分页。"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

if TYPE_CHECKING:
    from .report_data import ReportData

logger = logging.getLogger(__name__)

_FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_CN_FONT = "Helvetica"


def _register_fonts() -> str:
    global _CN_FONT
    for path in _FONT_CANDIDATES:
        try:
            pdfmetrics.registerFont(TTFont("NailCN", path))
            _CN_FONT = "NailCN"
            return "NailCN"
        except Exception:
            continue
    return "Helvetica"


_register_fonts()


def build_daily_report_pdf(report: "ReportData", charts: dict[str, BytesIO | None]) -> bytes:
    try:
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=20 * mm, rightMargin=20 * mm,
                                topMargin=18 * mm, bottomMargin=18 * mm)
        story: list = []

        # P1
        story.extend(_build_cover(report))
        story.append(Spacer(1, 6 * mm))
        story.extend(_build_metrics_cards(report))
        story.append(Spacer(1, 5 * mm))

        if charts.get("trend"):
            story.append(Image(charts["trend"], width=170 * mm, height=59 * mm))
            story.append(Spacer(1, 5 * mm))

        story.extend(_build_top5_table(report))
        story.append(PageBreak())

        # P2
        if charts.get("style"):
            story.append(Image(charts["style"], width=95 * mm, height=95 * mm))
        story.append(Spacer(1, 4 * mm))

        if charts.get("behavior"):
            story.append(Image(charts["behavior"], width=170 * mm, height=40 * mm))
        story.append(Spacer(1, 5 * mm))

        story.extend(_build_cold_table(report))
        story.append(PageBreak())

        # P3
        story.extend(_build_strategy(report))
        story.append(Spacer(1, 8 * mm))
        story.append(HRFlowable(width="100%", color=HexColor("#E5E7EB")))
        story.append(Spacer(1, 4 * mm))
        story.extend(_build_meta(report))

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        logger.exception("PDF build failed, returning fallback")
        return _build_fallback_pdf(report, str(e))


def _build_cover(report: "ReportData") -> list:
    styles = getSampleStyleSheet()
    title = Paragraph("nailflow 美甲运营日报",
        ParagraphStyle("T", parent=styles["Title"], fontName=_CN_FONT,
                        fontSize=24, textColor=HexColor("#EC4899"), spaceAfter=4 * mm))
    subtitle = Paragraph(f"{report.date}　|　近{report.days}日趋势",
        ParagraphStyle("ST", parent=styles["Normal"], fontName=_CN_FONT,
                        fontSize=12, textColor=HexColor("#6B7280")))
    return [title, subtitle, Spacer(1, 2 * mm),
            HRFlowable(width="100%", thickness=1.5, color=HexColor("#EC4899"))]


def _build_metrics_cards(report: "ReportData") -> list:
    m = report.metrics
    data = [["总信号数", "活跃用户", "爆款数", "冷门预警"],
            [str(m.total_signals), str(m.active_users), str(m.hot_count), str(m.cold_count)]]
    t = Table(data, colWidths=[42 * mm] * 4)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), _CN_FONT),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#6B7280")),
        ("FONTNAME", (0, 1), (-1, 1), _CN_FONT),
        ("FONTSIZE", (0, 1), (-1, 1), 22),
        ("TEXTCOLOR", (0, 1), (-1, 1), HexColor("#111827")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F9FAFB")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [t]


def _build_top5_table(report: "ReportData") -> list:
    styles = getSampleStyleSheet()
    heading = Paragraph("\U0001F3C6 爆款 TOP5",
        ParagraphStyle("H3", parent=styles["Heading3"], fontName=_CN_FONT,
                        fontSize=14, textColor=HexColor("#111827"), spaceBefore=4 * mm, spaceAfter=3 * mm))
    rows = [["排名", "款式ID", "信号数", "变化"]]
    for s in report.top_styles:
        ch = f"↑{s.change_pct:.0f}%" if s.change_pct > 0 else f"↓{abs(s.change_pct):.0f}%"
        rows.append([str(s.rank), s.style_id, str(s.signal_count), ch])
    t = Table(rows, colWidths=[15 * mm, 70 * mm, 35 * mm, 45 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _CN_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#374151")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F9FAFB")]),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#E5E7EB")),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [heading, t]


def _build_cold_table(report: "ReportData") -> list:
    styles = getSampleStyleSheet()
    heading = Paragraph("⚠️ 冷门预警",
        ParagraphStyle("H3", parent=styles["Heading3"], fontName=_CN_FONT,
                        fontSize=14, textColor=HexColor("#D97706"), spaceBefore=4 * mm, spaceAfter=3 * mm))
    if not report.cold_styles:
        return [heading, Paragraph("本周无冷门预警。",
            ParagraphStyle("N", parent=styles["Normal"], fontName=_CN_FONT, fontSize=10))]
    rows = [["款式ID", "信号数", "变化"]]
    for s in report.cold_styles:
        ch = f"↓{abs(s.change_pct):.0f}%" if s.change_pct < 0 else "-"
        rows.append([s.style_id, str(s.signal_count), ch])
    t = Table(rows, colWidths=[75 * mm, 45 * mm, 45 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), _CN_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#FEF3C7")),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return [heading, t]


def _build_strategy(report: "ReportData") -> list:
    styles = getSampleStyleSheet()
    heading = Paragraph("\U0001F4A1 运营策略建议",
        ParagraphStyle("H3", parent=styles["Heading3"], fontName=_CN_FONT,
                        fontSize=14, textColor=HexColor("#111827"), spaceAfter=4 * mm))
    body = Paragraph(report.strategy_text.replace("\n", "<br/>"),
        ParagraphStyle("Body", parent=styles["Normal"], fontName=_CN_FONT,
                        fontSize=10, leading=16, textColor=HexColor("#374151")))
    return [heading, body]


def _build_meta(report: "ReportData") -> list:
    styles = getSampleStyleSheet()
    lines = [
        f"数据来源: {report.data_source}",
        f"生成时间: {report.generated_at}",
        f"分析模型: {report.model_used}",
        "本报告由 NailOps Channel 自动生成",
    ]
    items = []
    for line in lines:
        items.append(Paragraph(line,
            ParagraphStyle("Meta", parent=styles["Normal"], fontName=_CN_FONT,
                            fontSize=8, textColor=HexColor("#9CA3AF"))))
        items.append(Spacer(1, 1.5 * mm))
    return items


def _build_fallback_pdf(report: "ReportData", error_msg: str) -> bytes:
    try:
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph("nailflow 运营日报（简化版）",
                      ParagraphStyle("T", parent=styles["Title"], fontName=_CN_FONT, fontSize=18)),
            Spacer(1, 8 * mm),
            Paragraph(report.strategy_text or "数据暂时不可用。",
                      ParagraphStyle("B", parent=styles["Normal"], fontName=_CN_FONT, fontSize=10)),
            Spacer(1, 10 * mm),
            Paragraph(f"生成失败: {error_msg}",
                      ParagraphStyle("E", parent=styles["Normal"], fontName=_CN_FONT,
                                     fontSize=8, textColor=HexColor("#9CA3AF"))),
        ]
        doc.build(story)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return b""
