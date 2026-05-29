# backend/packages/harness/deerflow/tools/nail/base.py
"""Shared utilities for NailFlow tools: DB connection, paths, table initialization."""
import contextlib
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 路径常量（均从环境变量读取，有合理默认值）──────────────────
UPLOADS_DIR: Path = Path(os.getenv("NAIL_UPLOADS_DIR", "data/uploads"))
RESULTS_DIR: Path = Path(os.getenv("NAIL_RESULTS_DIR", "data/results"))
DB_PATH: Path = Path(os.getenv("NAIL_DB_PATH", "data/nailflow.db"))

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextlib.contextmanager
def get_db():
    """SQLite 连接上下文管理器。

    用法：
        with get_db() as conn:
            conn.execute(...)
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_nail_tables() -> None:
    """幂等建表：不存在时创建 NailFlow 所需的 6 张表。"""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS nail_runs (
                id          TEXT PRIMARY KEY,
                user_id     TEXT,
                nail_role   TEXT,
                intent      TEXT,
                status      TEXT DEFAULT 'running',
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS nail_assets (
                id          TEXT PRIMARY KEY,
                run_id      TEXT,
                asset_type  TEXT,
                file_path   TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ops_signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT,
                style_id    TEXT,
                signal_type TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS action_proposals (
                id           TEXT PRIMARY KEY,
                run_id       TEXT,
                title        TEXT,
                content      TEXT,
                status       TEXT DEFAULT 'pending',
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                confirmed_at DATETIME
            );

            CREATE TABLE IF NOT EXISTS evaluation_results (
                id              TEXT PRIMARY KEY,
                run_id          TEXT,
                total_score     INTEGER,
                rubric_scores   TEXT,
                blocking_issues TEXT,
                next_dev_tasks  TEXT,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS ops_memory (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type  TEXT,
                content      TEXT,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS nail_model_configs (
                id                TEXT PRIMARY KEY,
                name              TEXT UNIQUE NOT NULL,
                display_name      TEXT NOT NULL,
                provider          TEXT NOT NULL,
                model_id          TEXT NOT NULL,
                api_key           TEXT,
                api_base          TEXT NOT NULL,
                use_class         TEXT NOT NULL,
                supports_vision   INTEGER DEFAULT 0,
                supports_thinking INTEGER DEFAULT 0,
                is_active         INTEGER DEFAULT 1,
                created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS nail_agent_configs (
                config_key  TEXT PRIMARY KEY,
                model_name  TEXT NOT NULL,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS nail_tool_overrides (
                tool_name   TEXT PRIMARY KEY,
                model_name  TEXT,
                is_enabled  INTEGER DEFAULT 1,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
    logger.info("NailFlow tables initialized at %s", DB_PATH)


def get_tool_model(tool_name: str) -> str | None:
    """读取工具的模型配置：先查工具覆盖，再查全局 tool_default，都没有返回 None。"""
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT model_name FROM nail_tool_overrides "
                "WHERE tool_name = ? AND is_enabled = 1",
                (tool_name,),
            ).fetchone()
            if row and row["model_name"]:
                return row["model_name"]
            default = conn.execute(
                "SELECT model_name FROM nail_agent_configs WHERE config_key = 'tool_default'"
            ).fetchone()
            return default["model_name"] if default else None
    except Exception as e:
        logger.debug("get_tool_model(%s) failed (DB not ready?): %s", tool_name, e)
        return None
