# NailOps PDF Report — 运营日报 PDF 导出实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 NailOps Channel 日报基础上增加 PDF 文件生成：matplotlib 图表 + ReportLab 拼装 → file_adapter 保存 → API 下载

**Architecture:** 三层：report_data (SQL聚合) → charts (PNG渲染) → builder (PDF拼装)。通过 FileMessage + FileAdapter 融入已有 delivery 管道。

**Tech Stack:** matplotlib 3.x / seaborn / ReportLab 4.x / SQLite (已有)

---

### Task 1: Install dependencies + FileMessage 类型

**Files:**
- Modify: `backend/packages/harness/nailflow/tools/nail/ops_channel/delivery/messages/base.py`

- [ ] **Step 1: Install pip dependencies**

```bash
cd backend && uv pip install matplotlib seaborn reportlab
```

- [ ] **Step 2: Add FileMessage to messages/base.py**

Append after the `CardMessage` class at end of file:

```python
@dataclass
class FileMessage(AbstractMessage):
    """文件消息：字节内容 + 文件名 + MIME 类型。"""
    content: bytes
    filename: str
    mime_type: str = "application/pdf"

    def __init__(self, content: bytes, filename: str, mime_type: str = "application/pdf"):
        self.kind = MessageKind.FILE    # type: ignore[call-arg]
        self.content = content
        self.filename = filename
        self.mime_type = mime_type

    def to_primitive(self) -> dict[str, Any]:
        return {
            "kind": "file",
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size": len(self.content),
        }
```

Note: Also add `"file"` to `MessageKind` enum:

```python
class MessageKind(Enum):
    TEXT = "text"
    CARD = "card"
    MARKDOWN = "markdown"
    TEMPLATE = "template"
    FILE = "file"          # 新增
```

- [ ] **Step 3: Verify**

```bash
cd backend && uv run python -c "
from packages.harness.nailflow.tools.nail.ops_channel.delivery.messages.base import FileMessage, MessageKind
m = FileMessage(b'hello', 'test.txt', 'text/plain')
assert m.kind == MessageKind.FILE
assert m.filename == 'test.txt'
print('FileMessage OK')
"
```
Expected: `FileMessage OK`

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/nailflow/tools/nail/ops_channel/delivery/messages/base.py
git commit -m "feat(pdf-report): add FileMessage type + install matplotlib/seaborn/reportlab"
```

---

### Task 2: report_data.py — 数据聚合层

**Files:**
- Create: `backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report/__init__.py`
- Create: `backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report/report_data.py`

- [ ] **Step 1: Create directory**

```bash
mkdir -p backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report
touch backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report/__init__.py
```

- [ ] **Step 2: Write report_data.py**

```python
# ops_channel/formatters/pdf_report/report_data.py
"""PDF 日报数据聚合：SQL 查询 + 已有工具复用 → ReportData。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    total_signals: int = 0
    hot_count: int = 0
    cold_count: int = 0
    active_users: int = 0


@dataclass
class TrendPoint:
    date_label: str = ""
    signal_count: int = 0
    save_count: int = 0


@dataclass
class StyleRank:
    rank: int = 0
    style_id: str = ""
    signal_count: int = 0
    change_pct: float = 0.0


@dataclass
class CategoryPct:
    label: str = ""
    count: int = 0
    percentage: float = 0.0


@dataclass
class BehaviorPct:
    label: str = ""
    count: int = 0


@dataclass
class ReportData:
    date: str = ""
    days: int = 7
    metrics: Metrics = field(default_factory=Metrics)
    trend_series: list[TrendPoint] = field(default_factory=list)
    top_styles: list[StyleRank] = field(default_factory=list)
    cold_styles: list[StyleRank] = field(default_factory=list)
    style_distribution: list[CategoryPct] = field(default_factory=list)
    behavior_distribution: list[BehaviorPct] = field(default_factory=list)
    strategy_text: str = ""
    data_source: str = ""
    generated_at: str = ""
    model_used: str = ""


def gather_report_data(days: int = 7) -> ReportData:
    """从各数据源聚合报告数据，单一入口函数。
    每个子查询独立 try/except，单个失败不影响其他。
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    report = ReportData(date=today, days=days, generated_at=generated,
                         data_source=f"近{days}日 ops_signals 表")

    # 1. 核心指标
    try:
        report.metrics = _query_metrics(days)
    except Exception as e:
        logger.warning("metrics query failed: %s", e)

    # 2. 趋势时序
    try:
        report.trend_series = _query_daily_trend(days)
    except Exception as e:
        logger.warning("trend query failed: %s", e)

    # 3. 排行榜 + 4. 风格分布 + 5. 行为分布
    try:
        report.top_styles, report.cold_styles = _query_rankings(days)
    except Exception as e:
        logger.warning("rankings query failed: %s", e)

    try:
        report.style_distribution = _query_style_distribution(days)
    except Exception as e:
        logger.warning("style dist query failed: %s", e)

    try:
        report.behavior_distribution = _query_behavior_distribution(days)
    except Exception as e:
        logger.warning("behavior dist query failed: %s", e)

    # 6. 策略文本 (复用已有工具)
    try:
        report.strategy_text = _get_strategy_text(days)
        report.model_used = "ops_analysis_tool"
    except Exception as e:
        logger.warning("strategy text failed: %s", e)
        report.strategy_text = "策略分析暂时不可用"

    return report


def _query_metrics(days: int) -> Metrics:
    from ....base import get_db
    with get_db() as conn:
        row = conn.execute("""
            SELECT COUNT(*) AS total, COUNT(DISTINCT user_id) AS users
            FROM ops_signals WHERE created_at >= datetime('now', ?)
        """, (f"-{days} days",)).fetchone()
        hot = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT style_id, COUNT(*) AS cnt FROM ops_signals
                WHERE created_at >= datetime('now', ?) GROUP BY style_id HAVING cnt >= 3
            )
        """, (f"-{days} days",)).fetchone()[0]
        cold = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT style_id, COUNT(*) AS cnt FROM ops_signals
                WHERE created_at >= datetime('now', ?) GROUP BY style_id HAVING cnt <= 1
            )
        """, (f"-{days} days",)).fetchone()[0]
    return Metrics(total_signals=row["total"] or 0, active_users=row["users"] or 0,
                    hot_count=hot or 0, cold_count=cold or 0)


def _query_daily_trend(days: int) -> list[TrendPoint]:
    from ....base import get_db
    with get_db() as conn:
        rows = conn.execute("""
            SELECT date(created_at) AS d, COUNT(*) AS total,
                   SUM(CASE WHEN signal_type='save' THEN 1 ELSE 0 END) AS saves
            FROM ops_signals WHERE created_at >= datetime('now', ?)
            GROUP BY d ORDER BY d
        """, (f"-{days} days",)).fetchall()
    return [TrendPoint(date_label=r["d"][-5:] if r["d"] else "",
                        signal_count=r["total"] or 0, save_count=r["saves"] or 0)
            for r in rows]


def _query_rankings(days: int) -> tuple[list[StyleRank], list[StyleRank]]:
    from ....base import get_db
    with get_db() as conn:
        rows = conn.execute("""
            SELECT style_id, COUNT(*) AS cnt FROM ops_signals
            WHERE created_at >= datetime('now', ?)
            GROUP BY style_id ORDER BY cnt DESC LIMIT 10
        """, (f"-{days} days",)).fetchall()

    now_total = sum(r["cnt"] for r in rows)

    # 前一周期对比
    prev_rows = {}
    try:
        prev = conn.execute("""
            SELECT style_id, COUNT(*) AS cnt FROM ops_signals
            WHERE created_at >= datetime('now', ?) AND created_at < datetime('now', ?)
            GROUP BY style_id
        """, (f"-{days*2} days", f"-{days} days")).fetchall()
        prev_rows = {r["style_id"]: r["cnt"] for r in prev}
    except Exception:
        pass

    top5 = []
    cold5 = []
    for i, r in enumerate(rows):
        sid = r["style_id"]
        cnt = r["cnt"]
        prev_cnt = prev_rows.get(sid, 0)
        change = ((cnt - prev_cnt) / max(prev_cnt, 1)) * 100 if prev_cnt > 0 else 100.0
        sr = StyleRank(rank=i + 1, style_id=sid, signal_count=cnt, change_pct=round(change, 1))
        if i < 5:
            top5.append(sr)
        if cnt <= 1 and len(cold5) < 5:
            cold5.append(sr)
    return top5, cold5


def _query_style_distribution(days: int) -> list[CategoryPct]:
    from ....base import get_db
    with get_db() as conn:
        rows = conn.execute("""
            SELECT COALESCE(c.category, '其他') AS cat, COUNT(*) AS cnt
            FROM ops_signals s LEFT JOIN nail_style_catalog c ON s.style_id = c.style_id
            WHERE s.created_at >= datetime('now', ?)
            GROUP BY cat ORDER BY cnt DESC
        """, (f"-{days} days",)).fetchall()
    total = sum(r["cnt"] for r in rows) or 1
    return [CategoryPct(label=r["cat"], count=r["cnt"],
                         percentage=round(r["cnt"] / total * 100, 1)) for r in rows]


def _query_behavior_distribution(days: int) -> list[BehaviorPct]:
    from ....base import get_db
    with get_db() as conn:
        rows = conn.execute("""
            SELECT signal_type, COUNT(*) AS cnt FROM ops_signals
            WHERE created_at >= datetime('now', ?)
            GROUP BY signal_type ORDER BY cnt DESC
        """, (f"-{days} days",)).fetchall()
    return [BehaviorPct(label=r["signal_type"], count=r["cnt"]) for r in rows]


def _get_strategy_text(days: int) -> str:
    import json
    from ....trend_discovery import trend_discovery_tool
    from ....ops_analysis import ops_analysis_tool

    trend_raw = trend_discovery_tool.run({"days": days})
    trend_data = json.loads(trend_raw)

    actions_raw = ops_analysis_tool.run({"trend_summary": json.dumps(trend_data, ensure_ascii=False)})
    actions_data = json.loads(actions_raw)

    lines = []
    for a in actions_data.get("marketing_actions", [])[:3]:
        title = a.get("title", "")
        reason = a.get("reason", "")
        metric = a.get("expected_metric", "")
        risk = a.get("risk", "")
        lines.append(f"• {title}")
        lines.append(f"  依据: {reason}")
        lines.append(f"  预期: {metric}　|　风险: {risk}")
        lines.append("")
    return "\n".join(lines) if lines else "本周暂无特殊运营建议。"
```

- [ ] **Step 3: Verify import**

```bash
cd backend && uv run python -c "
from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import gather_report_data, ReportData
r = gather_report_data(days=1)
print(f'Report: date={r.date}, metrics={r.metrics.total_signals} signals, {len(r.trend_series)} trend points')
print('report_data OK')
"
```
Expected: `Report: date=... metrics=0 signals, ... report_data OK`

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report/
git commit -m "feat(pdf-report): add report_data.py — SQL aggregation + LLM strategy"
```

---

### Task 3: charts.py — matplotlib 图表渲染

**Files:**
- Create: `backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report/charts.py`

- [ ] **Step 1: Write charts.py**

```python
# ops_channel/formatters/pdf_report/charts.py
"""matplotlib 图表渲染：面积图、环形图、柱状图。"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

if TYPE_CHECKING:
    from .report_data import TrendPoint, CategoryPct, BehaviorPct

logger = logging.getLogger(__name__)

# 全局样式
plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
try:
    plt.style.use("seaborn-v0_8-whitegrid")
except OSError:
    plt.style.use("ggplot")  # seaborn 不可用时的降级

BRAND_COLORS = {
    "primary":   "#EC4899",
    "secondary": "#3B82F6",
    "accent":    "#10B981",
    "warning":   "#F59E0B",
    "danger":    "#EF4444",
    "neutral":   "#6B7280",
}


def render_trend_chart(trend_series: list["TrendPoint"]) -> BytesIO | None:
    """7日趋势双层面积图。"""
    if not trend_series:
        return None
    try:
        fig, ax = plt.subplots(figsize=(10, 3.5))
        dates = [p.date_label for p in trend_series]
        totals = [p.signal_count for p in trend_series]
        saves = [p.save_count for p in trend_series]

        ax.fill_between(range(len(dates)), totals, alpha=0.15, color=BRAND_COLORS["primary"])
        ax.plot(range(len(dates)), totals, color=BRAND_COLORS["primary"],
                linewidth=2, marker="o", markersize=5, label="总信号")

        if any(s > 0 for s in saves):
            ax.fill_between(range(len(dates)), saves, alpha=0.25, color=BRAND_COLORS["accent"])
            ax.plot(range(len(dates)), saves, color=BRAND_COLORS["accent"],
                    linewidth=1.5, marker="s", markersize=4, label="收藏")

        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, fontsize=8)
        ax.set_ylabel("信号数", fontsize=9)
        ax.legend(loc="upper left", fontsize=8, frameon=True)
        ax.set_xlim(-0.3, len(dates) - 0.7)

        # seaborn despine 降级
        try:
            import seaborn as sns
            sns.despine()
        except ImportError:
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.warning("render_trend_chart failed: %s", e)
        return None


def render_style_donut(distribution: list["CategoryPct"]) -> BytesIO | None:
    """风格分布环形图。"""
    if not distribution:
        return None
    try:
        main = [d for d in distribution if d.percentage >= 5]
        other_pct = sum(d.percentage for d in distribution if d.percentage < 5)
        if other_pct > 0:
            # 临时创建一个 dataclass-like 对象
            class _FakePct:
                def __init__(self, label, percentage):
                    self.label = label; self.percentage = percentage
            main.append(_FakePct("其他", other_pct))  # type: ignore[arg-type]

        labels = [d.label for d in main]
        sizes = [d.percentage for d in main]
        colors = [BRAND_COLORS["primary"], BRAND_COLORS["secondary"],
                  BRAND_COLORS["accent"], BRAND_COLORS["warning"],
                  BRAND_COLORS["neutral"], BRAND_COLORS["danger"],
                  "#8B5CF6", "#06B6D4"][:len(main)]

        fig, ax = plt.subplots(figsize=(5, 5))
        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct="%1.1f%%",
            startangle=90, pctdistance=0.82,
            colors=colors, wedgeprops=dict(width=0.4, edgecolor="white", linewidth=1),
        )
        for at in autotexts:
            at.set_fontsize(8)
        ax.legend(wedges, [f"{l} ({p:.1f}%)" for l, p in zip(labels, sizes)],
                  loc="center left", bbox_to_anchor=(1, 0.5), fontsize=9, frameon=False)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.warning("render_style_donut failed: %s", e)
        return None


def render_behavior_bar(distribution: list["BehaviorPct"]) -> BytesIO | None:
    """用户行为水平柱状图。"""
    if not distribution:
        return None
    try:
        labels = [d.label for d in distribution]
        counts = [d.count for d in distribution]
        bar_colors = [BRAND_COLORS["primary"], BRAND_COLORS["secondary"],
                      BRAND_COLORS["accent"], BRAND_COLORS["warning"],
                      "#8B5CF6"][:len(labels)]

        fig, ax = plt.subplots(figsize=(7, 2.5))
        bars = ax.barh(labels, counts, color=bar_colors, height=0.55, edgecolor="white")
        ax.bar_label(bars, fontsize=9, padding=3)
        ax.set_xlabel("信号数", fontsize=9)
        ax.invert_yaxis()

        try:
            import seaborn as sns
            sns.despine()
        except ImportError:
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.warning("render_behavior_bar failed: %s", e)
        return None
```

- [ ] **Step 2: Verify import (no data needed)**

```bash
cd backend && uv run python -c "
from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.charts import render_trend_chart, render_style_donut, render_behavior_bar
print('charts.py imported OK')
"
```
Expected: `charts.py imported OK`

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report/charts.py
git commit -m "feat(pdf-report): add charts.py — matplotlib trend/ donut/ bar charts"
```

---

### Task 4: builder.py — ReportLab PDF 拼装

**Files:**
- Create: `backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report/builder.py`

- [ ] **Step 1: Write builder.py**

```python
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
    ("/System/Library/Fonts/PingFang.ttc", "PingFang.ttc"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "NotoSansCJK.ttc"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"),
]

_CN_FONT = "Helvetica"


def _register_fonts() -> str:
    global _CN_FONT
    for path, _name in _FONT_CANDIDATES:
        try:
            pdfmetrics.registerFont(TTFont("NailCN", path))
            _CN_FONT = "NailCN"
            return "NailCN"
        except Exception:
            continue
    _CN_FONT = "Helvetica"
    return "Helvetica"


_register_fonts()


def build_daily_report_pdf(report: "ReportData", charts: dict[str, BytesIO | None]) -> bytes:
    """主入口：拼装完整 PDF 日报，返回 PDF bytes。

    Args:
        report: 聚合好的结构化数据。
        charts: {"trend": BytesIO|None, "style": BytesIO|None, "behavior": BytesIO|None}
    """
    try:
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=18*mm, bottomMargin=18*mm)
        story: list = []

        # P1
        story.extend(_build_cover(report))
        story.append(Spacer(1, 6*mm))
        story.extend(_build_metrics_cards(report))
        story.append(Spacer(1, 5*mm))

        if charts.get("trend"):
            story.append(Image(charts["trend"], width=170*mm, height=59*mm))
            story.append(Spacer(1, 5*mm))

        story.extend(_build_top5_table(report))
        story.append(PageBreak())

        # P2
        if charts.get("style"):
            story.append(Image(charts["style"], width=95*mm, height=95*mm))
        story.append(Spacer(1, 4*mm))

        if charts.get("behavior"):
            story.append(Image(charts["behavior"], width=170*mm, height=40*mm))
        story.append(Spacer(1, 5*mm))

        story.extend(_build_cold_table(report))
        story.append(PageBreak())

        # P3
        story.extend(_build_strategy(report))
        story.append(Spacer(1, 8*mm))
        story.append(HRFlowable(width="100%", color=HexColor("#E5E7EB")))
        story.append(Spacer(1, 4*mm))
        story.extend(_build_meta(report))

        doc.build(story)
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        logger.exception("PDF build failed, returning fallback")
        return _build_fallback_pdf(report, str(e))


def _build_cover(report: "ReportData") -> list:
    styles = getSampleStyleSheet()
    title = Paragraph("NailFlow 美甲运营日报",
        ParagraphStyle("T", parent=styles["Title"], fontName=_CN_FONT,
                        fontSize=24, textColor=HexColor("#EC4899"), spaceAfter=4*mm))
    subtitle = Paragraph(f"{report.date}　|　近{report.days}日趋势",
        ParagraphStyle("ST", parent=styles["Normal"], fontName=_CN_FONT,
                        fontSize=12, textColor=HexColor("#6B7280")))
    return [title, subtitle, Spacer(1, 2*mm),
            HRFlowable(width="100%", thickness=1.5, color=HexColor("#EC4899"))]


def _build_metrics_cards(report: "ReportData") -> list:
    m = report.metrics
    data = [["总信号数", "活跃用户", "爆款数", "冷门预警"],
            [str(m.total_signals), str(m.active_users), str(m.hot_count), str(m.cold_count)]]
    t = Table(data, colWidths=[42*mm]*4)
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
    heading = Paragraph("🏆 爆款 TOP5",
        ParagraphStyle("H3", parent=styles["Heading3"], fontName=_CN_FONT,
                        fontSize=14, textColor=HexColor("#111827"), spaceBefore=4*mm, spaceAfter=3*mm))
    rows = [["排名", "款式ID", "信号数", "变化"]]
    for s in report.top_styles:
        ch = f"↑{s.change_pct:.0f}%" if s.change_pct > 0 else f"↓{abs(s.change_pct):.0f}%"
        rows.append([str(s.rank), s.style_id, str(s.signal_count), ch])
    t = Table(rows, colWidths=[15*mm, 70*mm, 35*mm, 45*mm])
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
                        fontSize=14, textColor=HexColor("#D97706"), spaceBefore=4*mm, spaceAfter=3*mm))
    if not report.cold_styles:
        return [heading, Paragraph("本周无冷门预警。",
            ParagraphStyle("N", parent=styles["Normal"], fontName=_CN_FONT, fontSize=10))]
    rows = [["款式ID", "信号数", "变化"]]
    for s in report.cold_styles:
        ch = f"↓{abs(s.change_pct):.0f}%" if s.change_pct < 0 else "-"
        rows.append([s.style_id, str(s.signal_count), ch])
    t = Table(rows, colWidths=[75*mm, 45*mm, 45*mm])
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
    heading = Paragraph("💡 运营策略建议",
        ParagraphStyle("H3", parent=styles["Heading3"], fontName=_CN_FONT,
                        fontSize=14, textColor=HexColor("#111827"), spaceAfter=4*mm))
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
        items.append(Spacer(1, 1.5*mm))
    return items


def _build_fallback_pdf(report: "ReportData", error_msg: str) -> bytes:
    """降级纯文本 PDF。"""
    try:
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        story = [
            Paragraph("NailFlow 运营日报（简化版）",
                      ParagraphStyle("T", parent=styles["Title"], fontName=_CN_FONT, fontSize=18)),
            Spacer(1, 8*mm),
            Paragraph(report.strategy_text or "数据暂时不可用。",
                      ParagraphStyle("B", parent=styles["Normal"], fontName=_CN_FONT, fontSize=10)),
            Spacer(1, 10*mm),
            Paragraph(f"生成失败: {error_msg}",
                      ParagraphStyle("E", parent=styles["Normal"], fontName=_CN_FONT,
                                     fontSize=8, textColor=HexColor("#9CA3AF"))),
        ]
        doc.build(story)
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        # 最终降级：返回空 PDF bytes
        return b""
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "
from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.builder import build_daily_report_pdf
print('builder.py imported OK')
"
```
Expected: `builder.py imported OK`

- [ ] **Step 3: Smoke test — generate a minimal PDF with no data**

```bash
cd backend && uv run python -c "
from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import ReportData, Metrics
from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.builder import build_daily_report_pdf
r = ReportData(date='2026-06-07', days=7, strategy_text='测试策略文本\n第二行')
pdf = build_daily_report_pdf(r, {})
assert len(pdf) > 100, f'PDF too small: {len(pdf)} bytes'
# Check PDF header
assert pdf[:5] == b'%PDF-', f'Not a valid PDF: {pdf[:20]}'
print(f'PDF generated: {len(pdf)} bytes')
"
```
Expected: `PDF generated: ... bytes`

- [ ] **Step 4: Commit**

```bash
git add backend/packages/harness/nailflow/tools/nail/ops_channel/formatters/pdf_report/builder.py
git commit -m "feat(pdf-report): add builder.py — ReportLab PDF assembly with fallback"
```

---

### Task 5: file_adapter.py — 文件输出适配器

**Files:**
- Create: `backend/packages/harness/nailflow/tools/nail/ops_channel/delivery/adapters/file_adapter.py`

- [ ] **Step 1: Write file_adapter.py**

```python
# ops_channel/delivery/adapters/file_adapter.py
"""文件输出适配器：将 FileMessage 写入磁盘。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ..base import AbstractChannelAdapter, ChannelCapability, DeliveryResult, DeliveryTarget

if TYPE_CHECKING:
    from ..messages.base import FileMessage, AbstractMessage

logger = logging.getLogger(__name__)


class FileAdapter(AbstractChannelAdapter):
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self._output_dir = Path(cfg.get("output_dir", "data/reports"))

    @property
    def channel_id(self) -> str:
        return "file"

    @property
    def capabilities(self) -> ChannelCapability:
        return ChannelCapability.FILE

    async def send(self, target: DeliveryTarget, message: "AbstractMessage") -> DeliveryResult:
        from ..messages.base import FileMessage

        if not isinstance(message, FileMessage):
            return DeliveryResult(ok=False, channel="file",
                error=f"FileAdapter expects FileMessage, got {type(message).__name__}")

        out_dir = Path(target.recipient) if target.recipient else self._output_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        filepath = out_dir / message.filename
        try:
            filepath.write_bytes(message.content)
            logger.info("FileAdapter: saved %s (%d bytes)", filepath, len(message.content))
            return DeliveryResult(ok=True, channel="file", message_id=str(filepath))
        except Exception as e:
            logger.error("FileAdapter write failed: %s", e)
            return DeliveryResult(ok=False, channel="file", error=str(e))
```

- [ ] **Step 2: Verify import**

```bash
cd backend && uv run python -c "
from packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.file_adapter import FileAdapter
a = FileAdapter(config={'output_dir': '/tmp/test_reports'})
assert a.channel_id == 'file'
print('file_adapter OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add backend/packages/harness/nailflow/tools/nail/ops_channel/delivery/adapters/file_adapter.py
git commit -m "feat(pdf-report): add file_adapter.py — file output channel adapter"
```

---

### Task 6: Integration — ops_runner + scheduler + app.py + nail_ops.py + config

**Files:**
- Modify: `backend/packages/harness/nailflow/tools/nail/ops_channel/ops_runner.py`
- Modify: `backend/packages/harness/nailflow/tools/nail/ops_channel/ops_scheduler.py`
- Modify: `backend/app/gateway/app.py`
- Modify: `backend/app/gateway/routers/nail_ops.py`
- Modify: `config.yaml`

- [ ] **Step 1: Modify ops_runner.py — add PDF generation to _run_daily_report**

In `_run_daily_report`, after the card is created and before the return, add PDF generation. Replace the return statement:

Old (around the end of _run_daily_report):
```python
    return {"message": card, "result_data": {"trend": trend_data, "actions": actions_data}, "ok": True, "error": ""}
```

New:
```python
    # PDF 生成
    pdf_message = None
    try:
        from .formatters.pdf_report.report_data import gather_report_data
        from .formatters.pdf_report.charts import render_trend_chart, render_style_donut, render_behavior_bar
        from .formatters.pdf_report.builder import build_daily_report_pdf
        from ..delivery.messages.base import FileMessage

        report_data = gather_report_data(days=days)
        charts = {
            "trend": render_trend_chart(report_data.trend_series),
            "style": render_style_donut(report_data.style_distribution),
            "behavior": render_behavior_bar(report_data.behavior_distribution),
        }
        pdf_bytes = build_daily_report_pdf(report_data, charts)
        pdf_filename = f"daily_report_{report_data.date}.pdf"
        pdf_message = FileMessage(content=pdf_bytes, filename=pdf_filename)
    except Exception as e:
        logger.warning("PDF generation failed: %s", e)

    return {
        "message": card,
        "pdf_message": pdf_message,
        "result_data": {"trend": trend_data, "actions": actions_data},
        "ok": True,
        "error": "",
    }
```

- [ ] **Step 2: Modify ops_scheduler.py — delivery loop handle pdf_message**

In `_execute_job`, the delivery loop must select the right message for the file channel. Find the section:

```python
        for target_spec in job.delivery.targets:
            from .delivery.base import DeliveryTarget
            target = DeliveryTarget(channel=target_spec["channel"], recipient=target_spec.get("recipient", ""))
            message = result.get("message")
            if message is None:
                continue
```

Replace with:

```python
        for target_spec in job.delivery.targets:
            from .delivery.base import DeliveryTarget
            target = DeliveryTarget(channel=target_spec["channel"], recipient=target_spec.get("recipient", ""))
            # file 通道投递 pdf_message，其他通道投递 message
            message = result.get("pdf_message") if target.channel == "file" else result.get("message")
            if message is None:
                continue
```

- [ ] **Step 3: Modify app.py lifespan — add file delivery target to daily_job**

In `app.py`, find the `daily_job` definition. Add the file target to delivery:

```python
                daily_job = OpsJob(
                    job_id="daily_report",
                    trigger=Trigger(type=TriggerType.CRON, cron_expr="0 9 * * *"),
                    task=TaskSpec(type="daily_report"),
                    delivery=DeliverySpec(targets=[
                        {"channel": "web_push", "recipient": "all"},
                        {"channel": "feishu", "recipient": feishu_webhook},
                        {"channel": "file", "recipient": "data/reports"},
                    ]),
                )
```

- [ ] **Step 4: Add API endpoints to nail_ops.py**

Append before the last line:

```python
# ─── PDF 报告下载 ──────────────────────────────────────────

@router.get("/ops/reports/latest")
async def get_latest_report():
    """下载最新 PDF 日报。"""
    reports_dir = Path("data/reports")
    if not reports_dir.exists():
        raise HTTPException(status_code=404, detail="No reports yet")
    pdfs = sorted(reports_dir.glob("daily_report_*.pdf"), reverse=True)
    if not pdfs:
        raise HTTPException(status_code=404, detail="No reports yet")
    return FileResponse(str(pdfs[0]), media_type="application/pdf", filename=pdfs[0].name)


@router.get("/ops/reports")
async def list_reports():
    """列出所有已生成的 PDF 日报。"""
    reports_dir = Path("data/reports")
    if not reports_dir.exists():
        return {"reports": []}
    pdfs = sorted(reports_dir.glob("daily_report_*.pdf"), reverse=True)
    return {
        "reports": [{"filename": p.name, "size": p.stat().st_size,
                      "created_at": p.stat().st_mtime} for p in pdfs[:30]]
    }
```

- [ ] **Step 5: Add file channel to config.yaml**

In `config.yaml`, under `nail_ops_channel.delivery.channels`, add after `web_push`:

```yaml
      file:
        adapter: "packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.file_adapter:FileAdapter"
        enabled: true
        config:
          output_dir: "data/reports"
```

- [ ] **Step 6: Verify full import chain**

```bash
cd backend && uv run python -c "
from packages.harness.nailflow.tools.nail.ops_channel import OpsScheduler, OpsJob, TaskSpec, Trigger, TriggerType, DeliverySpec, AdapterRegistry, ChannelRouter, run_job
from packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.file_adapter import FileAdapter
from packages.harness.nailflow.tools.nail.ops_channel.delivery.messages.base import FileMessage
print('Full integration import OK')
"
```
Expected: `Full integration import OK`

- [ ] **Step 7: Dry-run full PDF pipeline**

```bash
cd backend && uv run python -c "
import asyncio, os
os.environ['FEISHU_OPS_WEBHOOK_URL'] = 'https://example.test'
from packages.harness.nailflow.tools.nail.ops_channel import OpsScheduler, OpsJob, TaskSpec, Trigger, TriggerType, DeliverySpec, AdapterRegistry, ChannelRouter, run_job
import packages.harness.nailflow.tools.nail.ops_channel.job_store as _js

job = OpsJob(
    job_id='pdf_test', trigger=Trigger(type=TriggerType.CRON, cron_expr='0 9 * * *'),
    task=TaskSpec(type='daily_report'),
    delivery=DeliverySpec(targets=[
        {'channel': 'web_push', 'recipient': 'all'},
        {'channel': 'file', 'recipient': '/tmp/nailops_test_reports'},
    ])
)
registry = AdapterRegistry()
registry.load_from_config({
    'web_push': {'adapter': 'packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.web_push:WebPushAdapter', 'enabled': True, 'config': {}},
    'file': {'adapter': 'packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.file_adapter:FileAdapter', 'enabled': True, 'config': {'output_dir': '/tmp/nailops_test_reports'}},
})
router = ChannelRouter(registry)
scheduler = OpsScheduler(runner=run_job, router=router, job_store=_js, jobs=[job])

async def test():
    scheduler.trigger('pdf_test', {'trigger_type': 'manual', 'days': 1})
    await asyncio.sleep(5)
    import glob
    pdfs = glob.glob('/tmp/nailops_test_reports/daily_report_*.pdf')
    print(f'PDFs generated: {len(pdfs)}')
    for p in pdfs:
        size = os.path.getsize(p)
        print(f'  {p}: {size} bytes')
        with open(p, 'rb') as f:
            assert f.read(4) == b'%PDF', f'{p} is not a valid PDF'
    assert len(pdfs) > 0, 'No PDF generated!'
    print('Full pipeline OK')
    scheduler.shutdown()

asyncio.run(test())
"
```
Expected: `PDFs generated: 1 ... Full pipeline OK`

- [ ] **Step 8: Commit**

```bash
git add backend/packages/harness/nailflow/tools/nail/ops_channel/ops_runner.py \
        backend/packages/harness/nailflow/tools/nail/ops_channel/ops_scheduler.py \
        backend/app/gateway/app.py \
        backend/app/gateway/routers/nail_ops.py \
        config.yaml
git commit -m "feat(pdf-report): integrate PDF generation into daily_report pipeline"
```

---

### Task 7: Tests

**Files:**
- Create: `backend/tests/test_nail_ops_pdf_report.py`

- [ ] **Step 1: Write test file** — (see complete test code below)

```python
# backend/tests/test_nail_ops_pdf_report.py
"""NailOps PDF Report 测试：数据聚合 / 图表渲染 / PDF 拼装 / 文件适配器 / 全链路。"""
from __future__ import annotations

import asyncio
import os
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _set_fake_feishu_env():
    old = os.environ.get("FEISHU_OPS_WEBHOOK_URL")
    os.environ["FEISHU_OPS_WEBHOOK_URL"] = "https://feishu-webhook.test/fake"
    yield
    if old is None:
        del os.environ["FEISHU_OPS_WEBHOOK_URL"]
    else:
        os.environ["FEISHU_OPS_WEBHOOK_URL"] = old


@pytest.fixture
def ensure_tables():
    from packages.harness.nailflow.tools.nail.base import init_nail_tables
    init_nail_tables()


class TestReportData:
    def test_report_data_defaults(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import ReportData
        r = ReportData()
        assert r.days == 7
        assert r.metrics.total_signals == 0

    def test_gather_report_data_no_signals(self, ensure_tables):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import gather_report_data
        r = gather_report_data(days=1)
        assert r.date != ""
        assert r.metrics.total_signals == 0
        assert r.strategy_text != ""  # 至少有降级文本

    def test_dataclasses(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import (
            Metrics, TrendPoint, StyleRank, CategoryPct, BehaviorPct,
        )
        m = Metrics(total_signals=100, hot_count=3, cold_count=2, active_users=42)
        assert m.total_signals == 100
        tp = TrendPoint(date_label="06-01", signal_count=50, save_count=10)
        assert tp.date_label == "06-01"
        sr = StyleRank(rank=1, style_id="cow_french", signal_count=89, change_pct=23.5)
        assert sr.change_pct == 23.5


class TestCharts:
    def test_render_trend_empty(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.charts import render_trend_chart
        assert render_trend_chart([]) is None

    def test_render_trend_with_data(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.charts import render_trend_chart
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import TrendPoint
        data = [TrendPoint(date_label="06-01", signal_count=100, save_count=30),
                TrendPoint(date_label="06-02", signal_count=120, save_count=40)]
        buf = render_trend_chart(data)
        assert buf is not None
        png_header = buf.read(8)
        assert png_header[:4] == b'\x89PNG'

    def test_render_style_donut_empty(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.charts import render_style_donut
        assert render_style_donut([]) is None

    def test_render_behavior_bar_with_data(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.charts import render_behavior_bar
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import BehaviorPct
        data = [BehaviorPct(label="收藏", count=50), BehaviorPct(label="订单", count=30)]
        buf = render_behavior_bar(data)
        assert buf is not None
        assert buf.read(4) == b'\x89PNG'


class TestBuilder:
    def test_build_pdf_empty_report(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import ReportData
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.builder import build_daily_report_pdf
        r = ReportData(date="2026-06-07", days=7, strategy_text="测试")
        pdf = build_daily_report_pdf(r, {})
        assert pdf[:5] == b'%PDF-'
        assert len(pdf) > 200

    def test_build_pdf_with_charts(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import (
            ReportData, Metrics, TrendPoint, StyleRank, CategoryPct, BehaviorPct,
        )
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.charts import (
            render_trend_chart, render_style_donut, render_behavior_bar,
        )
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.builder import build_daily_report_pdf

        r = ReportData(
            date="2026-06-07",
            days=7,
            metrics=Metrics(total_signals=500, hot_count=3, cold_count=2, active_users=88),
            trend_series=[
                TrendPoint("06-01", 100, 30), TrendPoint("06-02", 120, 40), TrendPoint("06-03", 110, 35),
            ],
            top_styles=[StyleRank(1, "cow_french", 89, 23.5), StyleRank(2, "nude_cat", 67, 15.0)],
            cold_styles=[StyleRank(1, "glitter_grad", 2, -50.0)],
            style_distribution=[CategoryPct("法式", 50, 35.0), CategoryPct("猫眼", 30, 25.0)],
            behavior_distribution=[BehaviorPct("收藏", 200), BehaviorPct("订单", 120)],
            strategy_text="• 限时套餐\n  依据: 收藏信号高\n",
            data_source="test", generated_at="2026-06-07 09:00 UTC", model_used="test",
        )
        charts = {
            "trend": render_trend_chart(r.trend_series),
            "style": render_style_donut(r.style_distribution),
            "behavior": render_behavior_bar(r.behavior_distribution),
        }
        pdf = build_daily_report_pdf(r, charts)
        assert pdf[:5] == b'%PDF-'
        # with charts the PDF should be much bigger
        assert len(pdf) > 10000, f"Expected >10KB PDF, got {len(pdf)}"

    def test_fallback_pdf(self):
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.report_data import ReportData
        from packages.harness.nailflow.tools.nail.ops_channel.formatters.pdf_report.builder import build_daily_report_pdf
        # Trigger fallback by passing a non-chart object
        pdf = build_daily_report_pdf(ReportData(date="test", strategy_text="fallback test"), {"trend": "not_bytesio"})
        assert pdf[:5] == b'%PDF-'


class TestFileAdapter:
    def test_channel_id_and_caps(self):
        from packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.file_adapter import FileAdapter
        from packages.harness.nailflow.tools.nail.ops_channel.delivery.base import ChannelCapability as CC
        a = FileAdapter()
        assert a.channel_id == "file"
        assert CC.FILE in a.capabilities

    @pytest.mark.asyncio
    async def test_save_file(self, tmp_path):
        from packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.file_adapter import FileAdapter
        from packages.harness.nailflow.tools.nail.ops_channel.delivery.base import DeliveryTarget
        from packages.harness.nailflow.tools.nail.ops_channel.delivery.messages.base import FileMessage

        out_dir = tmp_path / "reports"
        a = FileAdapter(config={"output_dir": str(out_dir)})
        msg = FileMessage(b"hello pdf content", filename="test_report.pdf")
        result = await a.send(DeliveryTarget(channel="file", recipient=str(out_dir)), msg)
        assert result.ok
        saved = out_dir / "test_report.pdf"
        assert saved.exists()
        assert saved.read_bytes() == b"hello pdf content"

    @pytest.mark.asyncio
    async def test_reject_non_file_message(self):
        from packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.file_adapter import FileAdapter
        from packages.harness.nailflow.tools.nail.ops_channel.delivery.base import DeliveryTarget
        from packages.harness.nailflow.tools.nail.ops_channel.delivery.messages.base import TextMessage

        a = FileAdapter()
        result = await a.send(DeliveryTarget(channel="file", recipient="/tmp"), TextMessage("hi"))
        assert not result.ok
        assert "FileMessage" in result.error


class TestEndToEndPDFPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_pdf_generated(self, ensure_tables, tmp_path):
        from packages.harness.nailflow.tools.nail.ops_channel import (
            OpsScheduler, OpsJob, TaskSpec, Trigger, TriggerType, DeliverySpec,
            AdapterRegistry, ChannelRouter, run_job,
        )
        import packages.harness.nailflow.tools.nail.ops_channel.job_store as _js

        out_dir = tmp_path / "e2e_reports"

        job = OpsJob(
            job_id="e2e_pdf",
            trigger=Trigger(type=TriggerType.CRON, cron_expr="0 9 * * *"),
            task=TaskSpec(type="daily_report"),
            delivery=DeliverySpec(targets=[
                {"channel": "web_push", "recipient": "all"},
                {"channel": "file", "recipient": str(out_dir)},
            ]),
        )
        registry = AdapterRegistry()
        registry.load_from_config({
            "web_push": {
                "adapter": "packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.web_push:WebPushAdapter",
                "enabled": True, "config": {},
            },
            "file": {
                "adapter": "packages.harness.nailflow.tools.nail.ops_channel.delivery.adapters.file_adapter:FileAdapter",
                "enabled": True, "config": {"output_dir": str(out_dir)},
            },
        })
        router = ChannelRouter(registry)
        scheduler = OpsScheduler(runner=run_job, router=router, job_store=_js, jobs=[job])

        scheduler.trigger("e2e_pdf", {"trigger_type": "manual", "days": 1})
        await asyncio.sleep(5)

        pdfs = list(out_dir.glob("daily_report_*.pdf"))
        assert len(pdfs) >= 1, f"No PDF generated in {out_dir}"
        pdf_bytes = pdfs[0].read_bytes()
        assert pdf_bytes[:5] == b'%PDF-', f"Not a valid PDF: {pdfs[0]}"
        assert len(pdf_bytes) > 200

        # verify job_run status
        from packages.harness.nailflow.tools.nail.base import get_db
        with get_db() as conn:
            row = conn.execute(
                "SELECT status FROM ops_job_runs WHERE job_id='e2e_pdf' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            assert row["status"] == "delivered"

        scheduler.shutdown()
```

- [ ] **Step 2: Run tests**

```bash
cd backend && uv run python -m pytest tests/test_nail_ops_pdf_report.py -v --tb=short
```
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_nail_ops_pdf_report.py
git commit -m "test(pdf-report): add integration tests for PDF report generation"
```

---

## Verification Checklist

- [ ] `uv pip install matplotlib seaborn reportlab` — dependencies installed
- [ ] `FileMessage` renders `{"kind": "file", "filename": "...", ...}`
- [ ] `gather_report_data(days=1)` returns valid `ReportData` without crashing
- [ ] `render_trend_chart` returns valid PNG bytes
- [ ] `build_daily_report_pdf` with empty data returns valid PDF
- [ ] `build_daily_report_pdf` with charts returns >10KB PDF
- [ ] `FileAdapter.send` writes FileMessage bytes to disk
- [ ] `FileAdapter.send` rejects non-FileMessage
- [ ] E2E: trigger → trend_discovery + ops_analysis → PDF bytes → file saved to disk → job_run status=delivered
- [ ] `GET /api/nail/ops/reports/latest` returns 200 with PDF
- [ ] `GET /api/nail/ops/reports` returns report list
