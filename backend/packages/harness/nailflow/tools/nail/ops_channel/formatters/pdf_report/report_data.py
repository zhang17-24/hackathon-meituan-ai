# ops_channel/formatters/pdf_report/report_data.py
"""PDF 日报数据聚合：SQL 查询 + 已有工具复用 → ReportData。"""
from __future__ import annotations

import json
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
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    report = ReportData(date=today, days=days, generated_at=generated,
                         data_source=f"近{days}日 ops_signals 表")

    try:
        report.metrics = _query_metrics(days)
    except Exception as e:
        logger.warning("metrics query failed: %s", e)

    try:
        report.trend_series = _query_daily_trend(days)
    except Exception as e:
        logger.warning("trend query failed: %s", e)

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

    top5, cold5 = [], []
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
            SELECT signal_type AS st, COUNT(*) AS cnt FROM ops_signals
            WHERE created_at >= datetime('now', ?)
            GROUP BY st ORDER BY cnt DESC
        """, (f"-{days} days",)).fetchall()
    return [BehaviorPct(label=r["st"], count=r["cnt"]) for r in rows]


def _get_strategy_text(days: int) -> str:
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
