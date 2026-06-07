# ops_channel/ops_runner.py
"""Agent 层任务路由器：调用已有运营工具 + 格式化输出。"""
from __future__ import annotations

import json
import logging
from typing import Any

from .delivery.messages.base import AbstractMessage, TextMessage
from .job_store import OpsJob

logger = logging.getLogger(__name__)


async def run_job(job: OpsJob, trigger_context: dict | None = None) -> dict[str, Any]:
    ctx = trigger_context or {}
    task_type = job.task.type
    try:
        if task_type == "daily_report":
            return await _run_daily_report(ctx)
        elif task_type == "trend_alert":
            return await _run_trend_alert(ctx)
        elif task_type == "manual_ops":
            return await _run_manual_ops(ctx)
        elif task_type == "proactive_chat":
            return await _run_proactive_chat(job, ctx)
        else:
            return {"message": None, "result_data": {}, "ok": False, "error": f"Unknown task: {task_type}"}
    except Exception as e:
        logger.exception("run_job(%s) failed", job.job_id)
        return {"message": TextMessage(content=f"任务执行失败: {e}"), "result_data": {}, "ok": False, "error": str(e)}


async def _run_daily_report(ctx: dict) -> dict[str, Any]:
    from ..trend_discovery import trend_discovery_tool
    from ..ops_analysis import ops_analysis_tool
    from .formatters.daily_report import format_daily_report

    days = ctx.get("days", 7)

    trend_raw = trend_discovery_tool.run({"days": days})
    trend_data = json.loads(trend_raw)
    if trend_data.get("error"):
        return {"message": TextMessage(content=f"趋势分析失败: {trend_data['error']}"), "ok": False, "result_data": {}, "error": trend_data.get("error")}

    actions_raw = ops_analysis_tool.run({"trend_summary": json.dumps(trend_data, ensure_ascii=False)})
    actions_data = json.loads(actions_raw)

    card = format_daily_report(trend_data, actions_data, days)

    # PDF 生成
    pdf_message = None
    try:
        from .formatters.pdf_report.report_data import gather_report_data
        from .formatters.pdf_report.charts import render_trend_chart, render_style_donut, render_behavior_bar
        from .formatters.pdf_report.builder import build_daily_report_pdf
        from .delivery.messages.base import FileMessage

        report_data = gather_report_data(days=days)
        chart_bufs = {
            "trend": render_trend_chart(report_data.trend_series),
            "style": render_style_donut(report_data.style_distribution),
            "behavior": render_behavior_bar(report_data.behavior_distribution),
        }
        pdf_bytes = build_daily_report_pdf(report_data, chart_bufs)
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


async def _run_trend_alert(ctx: dict) -> dict[str, Any]:
    from .formatters.alert_card import format_trend_alert

    style_id = ctx.get("style_id", "")
    current_count = ctx.get("current_count", 0)
    baseline = ctx.get("baseline", 1.0)
    multiplier = current_count / max(baseline, 0.1)

    card = format_trend_alert(style_id=style_id, current_count=current_count, baseline=baseline, multiplier=round(multiplier, 1))

    return {"message": card, "result_data": {"style_id": style_id, "current_count": current_count, "baseline": baseline, "multiplier": multiplier}, "ok": True, "error": ""}


async def _run_manual_ops(ctx: dict) -> dict[str, Any]:
    user_message = ctx.get("user_message", "")

    if any(kw in user_message for kw in ["爆款", "趋势", "热门"]):
        from ..trend_discovery import trend_discovery_tool
        raw = trend_discovery_tool.run({"days": 7})
        data = json.loads(raw)
        hot = data.get("hot_styles", [])[:3]
        lines = [f"**近7日爆款 TOP{min(len(hot),3)}**", ""]
        for i, s in enumerate(hot, 1):
            lines.append(f"{i}. {s.get('style_id','?')} — {s.get('reason','')}")
        return {"message": TextMessage(content="\n".join(lines)), "ok": True, "result_data": {}, "error": ""}

    elif any(kw in user_message for kw in ["方案", "运营", "营销"]):
        from ..ops_analysis import ops_analysis_tool
        raw = ops_analysis_tool.run({"trend_summary": "", "query": user_message})
        data = json.loads(raw)
        actions = data.get("marketing_actions", [])
        lines = ["**运营建议**", ""]
        for a in actions:
            lines.append(f"· {a.get('title','')} — {a.get('reason','')}")
        return {"message": TextMessage(content="\n".join(lines)), "ok": True, "result_data": {}, "error": ""}

    else:
        return {"message": TextMessage(content=f"收到指令: {user_message}\n支持: 爆款趋势 / 运营方案"), "ok": True, "result_data": {}, "error": ""}


async def _run_proactive_chat(job: OpsJob, ctx: dict) -> dict[str, Any]:
    """执行 proactive_chat 任务：在指定的飞书会话 Thread 上运行 Agent。

    chat_id 来自 job.delivery.targets 中的 feishu 目标。
    如果 chat_id 已有 Thread，复用；否则创建新 Thread。
    """
    from .feishu_session import get_or_create_thread
    from .delivery.messages.base import TextMessage

    chat_id = ""
    for target_spec in job.delivery.targets:
        if target_spec.get("channel") == "feishu":
            chat_id = target_spec.get("chat_id", "")
            break

    if not chat_id:
        return {"message": TextMessage(content="proactive_chat 缺少 chat_id 配置"), "ok": False, "result_data": {}, "error": "missing chat_id"}

    prompt = ctx.get("prompt", "")
    if not prompt.strip():
        return {"message": TextMessage(content="proactive_chat 缺少 prompt"), "ok": False, "result_data": {}, "error": "missing prompt"}

    thread_id = get_or_create_thread(chat_id, "group")

    try:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"http://localhost:8001/api/v1/threads/{thread_id}/runs/stream",
                json={
                    "input": {
                        "messages": [{"role": "user", "content": prompt}],
                    },
                    "config": {
                        "configurable": {
                            "nail_role": "ops",
                            "nail_page_mode": "ops",
                        },
                    },
                },
            )
            resp.raise_for_status()

            accumulated = ""
            async for raw_line in resp.aiter_lines():
                if not raw_line.startswith("data: "):
                    continue
                try:
                    chunk = json.loads(raw_line[6:])
                except json.JSONDecodeError:
                    continue

                if isinstance(chunk.get("data"), list) and len(chunk["data"]) >= 2:
                    msg_type, msg_data = chunk["data"][0], chunk["data"][1]
                    if msg_type in ("ai", "AIMessageChunk"):
                        delta = ""
                        if isinstance(msg_data, dict):
                            delta = msg_data.get("content", "")
                            if isinstance(delta, list):
                                delta = "".join(
                                    d.get("text", "") if isinstance(d, dict) else str(d)
                                    for d in delta
                                )
                            elif not isinstance(delta, str):
                                delta = str(delta)
                        accumulated += delta

        return {
            "message": TextMessage(content=accumulated.strip()[:30000]),
            "result_data": {"chat_id": chat_id, "thread_id": thread_id},
            "ok": True,
            "error": "",
        }
    except Exception as e:
        logger.exception("proactive_chat failed for chat_id=%s", chat_id)
        return {"message": TextMessage(content=f"Proactive chat 执行失败: {e}"), "ok": False, "result_data": {}, "error": str(e)}
