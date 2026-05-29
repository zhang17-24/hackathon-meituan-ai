# backend/packages/harness/deerflow/tools/nail/base.py
"""Shared utilities for NailFlow tools: DB connection, paths, table initialization."""
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 路径常量（均从环境变量读取，有合理默认值）──────────────────
UPLOADS_DIR = Path(os.getenv("NAIL_UPLOADS_DIR", "data/uploads"))
RESULTS_DIR = Path(os.getenv("NAIL_RESULTS_DIR", "data/results"))
DB_PATH = Path(os.getenv("NAIL_DB_PATH", "data/nailflow.db"))

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_db() -> sqlite3.Connection:
    """返回带 row_factory 的 SQLite 连接（调用方负责关闭）。"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_nail_tables() -> None:
    """幂等建表：不存在时创建 NailFlow 所需的 6 张表。"""
    conn = get_db()
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
    """)
    conn.commit()
    conn.close()
    logger.info("NailFlow tables initialized at %s", DB_PATH)
