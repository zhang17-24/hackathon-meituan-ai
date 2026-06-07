# ops_channel/formatters/pdf_report/charts.py
"""matplotlib 图表渲染：面积图、环形图、柱状图。"""
from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from .report_data import TrendPoint, CategoryPct, BehaviorPct

logger = logging.getLogger(__name__)

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Hiragino Sans GB", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
try:
    plt.style.use("seaborn-v0_8-whitegrid")
except OSError:
    plt.style.use("ggplot")

BRAND_COLORS = {
    "primary": "#EC4899", "secondary": "#3B82F6", "accent": "#10B981",
    "warning": "#F59E0B", "danger": "#EF4444", "neutral": "#6B7280",
}


def _despine(ax):
    try:
        import seaborn as sns
        sns.despine()
    except ImportError:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)


def render_trend_chart(trend_series: list["TrendPoint"]) -> BytesIO | None:
    if not trend_series:
        return None
    try:
        fig, ax = plt.subplots(figsize=(10, 3.5))
        dates = [p.date_label for p in trend_series]
        totals = [p.signal_count for p in trend_series]
        saves = [p.save_count for p in trend_series]
        x = range(len(dates))

        ax.fill_between(x, totals, alpha=0.15, color=BRAND_COLORS["primary"])
        ax.plot(x, totals, color=BRAND_COLORS["primary"], linewidth=2, marker="o", markersize=5, label="总信号")

        if any(s > 0 for s in saves):
            ax.fill_between(x, saves, alpha=0.25, color=BRAND_COLORS["accent"])
            ax.plot(x, saves, color=BRAND_COLORS["accent"], linewidth=1.5, marker="s", markersize=4, label="收藏")

        ax.set_xticks(list(x))
        ax.set_xticklabels(dates, fontsize=8)
        ax.set_ylabel("信号数", fontsize=9)
        ax.legend(loc="upper left", fontsize=8, frameon=True)
        ax.set_xlim(-0.3, len(dates) - 0.7)
        _despine(ax)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.warning("render_trend_chart failed: %s", e)
        return None


def render_style_donut(distribution: list["CategoryPct"]) -> BytesIO | None:
    if not distribution:
        return None
    try:
        main = [d for d in distribution if d.percentage >= 5]
        other_pct = sum(d.percentage for d in distribution if d.percentage < 5)
        if other_pct > 0:
            main.append(_LabelPct("其他", other_pct))

        labels = [d.label for d in main]
        sizes = [d.percentage for d in main]
        palette = [BRAND_COLORS[k] for k in ["primary","secondary","accent","warning","neutral","danger"]]
        colors = (palette + ["#8B5CF6", "#06B6D4"])[:len(main)]

        fig, ax = plt.subplots(figsize=(5, 5))
        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct="%1.1f%%", startangle=90, pctdistance=0.82,
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
    if not distribution:
        return None
    try:
        labels = [d.label for d in distribution]
        counts = [d.count for d in distribution]
        palette = [BRAND_COLORS[k] for k in ["primary","secondary","accent","warning"]]
        bar_colors = (palette + ["#8B5CF6"])[:len(labels)]

        fig, ax = plt.subplots(figsize=(7, 2.5))
        bars = ax.barh(labels, counts, color=bar_colors, height=0.55, edgecolor="white")
        ax.bar_label(bars, fontsize=9, padding=3)
        ax.set_xlabel("信号数", fontsize=9)
        ax.invert_yaxis()
        _despine(ax)

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.warning("render_behavior_bar failed: %s", e)
        return None


class _LabelPct:
    """render_style_donut 中合并'其他'用的轻量容器。"""
    def __init__(self, label: str, percentage: float):
        self.label = label
        self.percentage = percentage
