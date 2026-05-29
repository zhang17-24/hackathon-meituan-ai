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

            CREATE TABLE IF NOT EXISTS tool_call_log (
                id          TEXT PRIMARY KEY,
                run_id      TEXT NOT NULL,
                tool_name   TEXT NOT NULL,
                call_index  INTEGER DEFAULT 0,
                input_json  TEXT,
                output_json TEXT,
                thinking    TEXT,
                duration_ms INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS nail_user_prefs (
                user_id     TEXT PRIMARY KEY,
                pref_vector TEXT NOT NULL,
                trial_count INTEGER DEFAULT 0,
                save_count  INTEGER DEFAULT 0,
                updated_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS nail_style_catalog (
                style_id    TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                category    TEXT,
                color_tags  TEXT,
                image_path  TEXT,
                source      TEXT DEFAULT 'static'
            );
        """)
    try:
        with get_db() as conn:
            conn.execute(
                "ALTER TABLE nail_tool_overrides ADD COLUMN enabled_pages TEXT DEFAULT '[\"tryon\",\"ops\",\"eval\"]'"
            )
    except Exception as _e:
        if "duplicate column name" not in str(_e):
            logger.warning("ALTER TABLE nail_tool_overrides failed: %s", _e)

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


def update_user_pref_vector(user_id: str, style_id: str, signal_type: str) -> None:
    """用加权滑动平均更新用户偏好向量。

    HISTORY_DECAY=0.8, NEW_SIGNAL_RATIO=0.2
    signal_weight: tryon=1.0, save=3.0, search=2.0
    """
    import json as _json
    try:
        import numpy as np
    except ImportError:
        logger.warning("numpy not installed, skipping pref vector update")
        return

    SIGNAL_WEIGHT = {"tryon": 1.0, "save": 3.0, "search": 2.0}
    HISTORY_DECAY = 0.8
    NEW_SIGNAL_RATIO = 0.2

    try:
        import chromadb
        from chromadb.utils import embedding_functions
        chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
        client = chromadb.PersistentClient(path=chroma_dir)
        ef = embedding_functions.DefaultEmbeddingFunction()
        col = client.get_or_create_collection("nail_styles", embedding_function=ef)

        result = col.get(ids=[style_id], include=["embeddings"])
        if not result["embeddings"]:
            logger.debug("update_user_pref_vector: style_id %s not in ChromaDB", style_id)
            return
        style_vec = np.array(result["embeddings"][0], dtype=float)

        with get_db() as conn:
            row = conn.execute(
                "SELECT pref_vector FROM nail_user_prefs WHERE user_id=?", (user_id,)
            ).fetchone()

        weight = SIGNAL_WEIGHT.get(signal_type, 1.0)

        if row is None:
            new_pref = style_vec * weight
        else:
            old_pref = np.array(_json.loads(row["pref_vector"]), dtype=float)
            new_pref = old_pref * HISTORY_DECAY + style_vec * NEW_SIGNAL_RATIO * weight

        norm = float(np.linalg.norm(new_pref))
        if norm > 0:
            new_pref = new_pref / norm

        with get_db() as conn:
            conn.execute("""
                INSERT INTO nail_user_prefs (user_id, pref_vector, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    pref_vector = excluded.pref_vector,
                    updated_at  = excluded.updated_at
            """, (user_id, _json.dumps(new_pref.tolist())))
            if signal_type == "tryon":
                conn.execute(
                    "UPDATE nail_user_prefs SET trial_count = trial_count + 1 WHERE user_id = ?",
                    (user_id,)
                )
            elif signal_type == "save":
                conn.execute(
                    "UPDATE nail_user_prefs SET save_count = save_count + 1 WHERE user_id = ?",
                    (user_id,)
                )
            # search 信号不计数

    except Exception as e:
        logger.error("update_user_pref_vector failed (user=%s style=%s): %s", user_id, style_id, e)
