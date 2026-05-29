# backend/nail_scheduler.py
"""NailFlow 运营端定时任务：每天 09:00 触发趋势分析并保存到 ops_memory。"""
import logging

logger = logging.getLogger(__name__)


def run_daily_trend_report() -> None:
    """每日定时任务：趋势分析 → 结果存入 ops_memory。"""
    import json
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))

        from packages.harness.deerflow.tools.nail.trend_discovery import trend_discovery_tool
        from packages.harness.deerflow.tools.nail.base import get_db

        result = trend_discovery_tool.run({"days": 7})
        data = json.loads(result)
        summary = data.get("trend_summary", "")

        with get_db() as conn:
            conn.execute(
                "INSERT INTO ops_memory (memory_type, content) VALUES ('marketing', ?)",
                (json.dumps({"type": "daily_trend", "summary": summary}, ensure_ascii=False),)
            )
            conn.commit()

        logger.info("Daily trend report saved to ops_memory: %s", summary[:50])
    except Exception as e:
        logger.error("Daily trend report failed: %s", e)


def start_scheduler():
    """启动 APScheduler 后台调度器。返回 scheduler 实例（用于优雅关闭）。"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        scheduler.add_job(run_daily_trend_report, "cron", hour=9, minute=0, id="daily_trend")
        scheduler.start()
        logger.info("NailFlow scheduler started — daily trend at 09:00")
        return scheduler
    except ImportError:
        logger.warning("APScheduler not installed. Run: pip install apscheduler")
        return None
    except Exception as e:
        logger.error("Scheduler start failed: %s", e)
        return None
