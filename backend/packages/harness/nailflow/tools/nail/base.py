# backend/packages/harness/nailflow/tools/nail/base.py
"""Shared utilities for nailflow tools: DB connection, paths, table initialization."""
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

# 美甲仓库子目录
HANDS_DIR = UPLOADS_DIR / "hands"
STYLES_DIR = UPLOADS_DIR / "styles"
HANDS_DIR.mkdir(parents=True, exist_ok=True)
STYLES_DIR.mkdir(parents=True, exist_ok=True)


def resolve_image_path(image_path: str) -> Path:
    """Resolve an image path that may be a virtual sandbox path or real path.

    Handles:
    - Direct filesystem paths
    - Virtual sandbox paths like /mnt/user-data/uploads/filename.png
    - nailflow thread upload paths
    - nailflow data/uploads/ fallback

    Returns the first existing resolved path, or the original as fallback.
    """
    p = Path(image_path)
    if p.exists():
        return p

    # Virtual sandbox path: /mnt/user-data/uploads/filename.png
    filename = p.name
    if not filename:
        return p

    # 1. Try nailflow data/uploads/
    alt = UPLOADS_DIR / filename
    if alt.exists():
        return alt

    # 2. Try nailflow data/results/
    alt = RESULTS_DIR / filename
    if alt.exists():
        return alt

    # 3. Search nailflow thread upload directories
    nailflow_base = Path(".nail-flow")
    if nailflow_base.exists():
        for up_dir in nailflow_base.glob("users/*/threads/*/user-data/uploads/"):
            candidate = up_dir / filename
            if candidate.exists():
                return candidate
        for ws_dir in nailflow_base.glob("users/*/threads/*/user-data/workspace/"):
            candidate = ws_dir / filename
            if candidate.exists():
                return candidate

    return p


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
    """幂等建表：不存在时创建 nailflow 所需的全部表。"""
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


            CREATE TABLE IF NOT EXISTS ops_memory (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type  TEXT,
                content      TEXT,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS feishu_sessions (
                chat_id     TEXT PRIMARY KEY,
                thread_id   TEXT NOT NULL,
                chat_type   TEXT DEFAULT 'group',
                created_at  TEXT DEFAULT (datetime('now')),
                last_active TEXT DEFAULT (datetime('now'))
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

            CREATE TABLE IF NOT EXISTS nail_user_prefs_v2 (
                user_id       TEXT PRIMARY KEY,
                pref_vector   TEXT NOT NULL,
                color_vector  TEXT,
                pattern_vector TEXT,
                style_tags    TEXT,
                occasion_tags TEXT,
                skin_tone_hex TEXT,
                hand_shape    TEXT,
                trial_count   INTEGER DEFAULT 0,
                save_count    INTEGER DEFAULT 0,
                embedding_version TEXT DEFAULT 'chinese-clip-v2',
                updated_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS nail_style_catalog (
                style_id    TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                category    TEXT,
                color_tags  TEXT,
                image_path  TEXT,
                source      TEXT DEFAULT 'static',
                color_group TEXT,
                pattern_type TEXT
            );

            CREATE TABLE IF NOT EXISTS nail_hand_photos (
                id          TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                filename    TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                thumbnail   TEXT,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS nail_style_images (
                id          TEXT PRIMARY KEY,
                user_id     TEXT,
                filename    TEXT NOT NULL,
                file_path   TEXT NOT NULL,
                thumbnail   TEXT,
                category    TEXT DEFAULT 'user',
                tags        TEXT,
                source      TEXT DEFAULT 'user',
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS nail_knowledge (
                topic_id    TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                summary     TEXT,
                content     TEXT,
                tags        TEXT,
                source      TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS community_posts (
                id            TEXT PRIMARY KEY,
                user_id       TEXT NOT NULL,
                content       TEXT NOT NULL DEFAULT '',
                tags          TEXT,
                style_refs    TEXT,
                like_count    INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                is_active     INTEGER DEFAULT 1,
                created_at    TEXT,
                updated_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS post_images (
                id         TEXT PRIMARY KEY,
                post_id    TEXT NOT NULL,
                file_path  TEXT NOT NULL,
                filename   TEXT,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS post_likes (
                id         TEXT PRIMARY KEY,
                post_id    TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS post_comments (
                id         TEXT PRIMARY KEY,
                post_id    TEXT NOT NULL,
                user_id    TEXT NOT NULL,
                content    TEXT NOT NULL,
                parent_id  TEXT,
                is_active  INTEGER DEFAULT 1,
                created_at TEXT
            );
        """)
    try:
        with get_db() as conn:
            conn.execute(
                "ALTER TABLE nail_tool_overrides ADD COLUMN enabled_pages TEXT DEFAULT '[\"tryon\",\"ops\"]'"
            )
    except Exception as _e:
        if "duplicate column name" not in str(_e):
            logger.warning("ALTER TABLE nail_tool_overrides failed: %s", _e)

    for sql in (
        "ALTER TABLE nail_style_catalog ADD COLUMN color_group TEXT",
        "ALTER TABLE nail_style_catalog ADD COLUMN pattern_type TEXT",
    ):
        try:
            with get_db() as conn:
                conn.execute(sql)
        except Exception as _e:
            if "duplicate column name" not in str(_e):
                logger.warning("ALTER TABLE nail_style_catalog failed: %s", _e)

    logger.info("nailflow tables initialized at %s", DB_PATH)


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
    """用加权滑动平均更新用户偏好向量（多模态 Chinese-CLIP 512d）。

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

        chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
        client = chromadb.PersistentClient(path=chroma_dir)
        col = client.get_or_create_collection("nail_styles", embedding_function=None)

        result = col.get(ids=[style_id], include=["embeddings"])
        embeddings = result.get("embeddings")
        if embeddings is None or len(embeddings) == 0:
            # 降级：从款式描述文本生成向量
            with get_db() as conn:
                row = conn.execute(
                    "SELECT description FROM nail_style_catalog WHERE style_id=?", (style_id,)
                ).fetchone()
            if row and row["description"]:
                from .embedding import encode_text
                style_vec = encode_text([row["description"]])[0]
            else:
                logger.debug("update_user_pref_vector: style_id %s not found in ChromaDB or catalog", style_id)
                return
        else:
            style_vec = np.array(result["embeddings"][0], dtype=float)

        # 统一维度为 512
        if len(style_vec) != 512:
            padded = np.zeros(512, dtype=float)
            padded[:min(len(style_vec), 512)] = style_vec[:min(len(style_vec), 512)]
            style_vec = padded

        with get_db() as conn:
            row = conn.execute(
                "SELECT pref_vector FROM nail_user_prefs WHERE user_id=?", (user_id,)
            ).fetchone()

        weight = SIGNAL_WEIGHT.get(signal_type, 1.0)

        if row is None:
            new_pref = style_vec * weight
        else:
            old_pref = np.array(_json.loads(row["pref_vector"]), dtype=float)
            if len(old_pref) != 512:
                padded = np.zeros(512, dtype=float)
                padded[:min(len(old_pref), 512)] = old_pref[:min(len(old_pref), 512)]
                old_pref = padded
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
            conn.commit()

        # 同步更新多维画像
        _update_multidim_profile(user_id, style_id, signal_type, weight, style_vec)

    except Exception as e:
        logger.error("update_user_pref_vector failed (user=%s style=%s): %s", user_id, style_id, e)


def _update_multidim_profile(user_id: str, style_id: str, signal_type: str, weight: float, style_vec) -> None:
    """更新多维度用户画像（颜色/图案/风格标签/场合）。"""
    import json as _json
    try:
        import numpy as np
    except ImportError:
        return

    HISTORY_DECAY = 0.8
    NEW_SIGNAL_RATIO = 0.2

    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT pref_vector, color_vector, pattern_vector, style_tags, occasion_tags "
                "FROM nail_user_prefs_v2 WHERE user_id=?", (user_id,)
            ).fetchone()

            # 读取款式的结构化特征
            style_row = conn.execute(
                "SELECT category, color_tags FROM nail_style_catalog WHERE style_id=?", (style_id,)
            ).fetchone()

        category = style_row["category"] if style_row else ""
        color_tags = style_row["color_tags"] if style_row else ""

        old_pref = None
        if row is not None:
            old_pref = np.array(_json.loads(row["pref_vector"]), dtype=float)
            if len(old_pref) != 512:
                padded = np.zeros(512, dtype=float)
                padded[:min(len(old_pref), 512)] = old_pref[:min(len(old_pref), 512)]
                old_pref = padded

        # 主偏好向量更新
        if old_pref is None:
            new_pref = style_vec * weight
        else:
            new_pref = old_pref * HISTORY_DECAY + style_vec * NEW_SIGNAL_RATIO * weight
        norm = float(np.linalg.norm(new_pref))
        if norm > 0:
            new_pref = new_pref / norm

        # 颜色向量：仅更新, 从 color_tags 文本编码
        color_vector_raw = None
        if color_tags:
            from .embedding import encode_text
            color_vec = encode_text(["美甲颜色: " + color_tags.replace(",", "、")])[0]
            color_vector_raw = _json.dumps(color_vec.tolist())

        # 图案偏好: 从 category 更新
        pattern_vector_raw = None
        if category:
            from .embedding import encode_text
            pattern_vec = encode_text(["美甲风格: " + category])[0]
            pattern_vector_raw = _json.dumps(pattern_vec.tolist())

        # 风格标签计数
        style_tags_data = {}
        if row and row["style_tags"]:
            try:
                style_tags_data = _json.loads(row["style_tags"])
            except (_json.JSONDecodeError, TypeError):
                style_tags_data = {}
        if category:
            style_tags_data[category] = style_tags_data.get(category, 0) + (1 if signal_type == "save" else 0.5)

        with get_db() as conn:
            conn.execute("""
                INSERT INTO nail_user_prefs_v2 (user_id, pref_vector, color_vector, pattern_vector,
                    style_tags, trial_count, save_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    pref_vector = excluded.pref_vector,
                    color_vector = COALESCE(excluded.color_vector, nail_user_prefs_v2.color_vector),
                    pattern_vector = COALESCE(excluded.pattern_vector, nail_user_prefs_v2.pattern_vector),
                    style_tags = COALESCE(excluded.style_tags, nail_user_prefs_v2.style_tags),
                    updated_at = excluded.updated_at
            """, (
                user_id,
                _json.dumps(new_pref.tolist()),
                color_vector_raw,
                pattern_vector_raw,
                _json.dumps(style_tags_data, ensure_ascii=False),
                1 if signal_type == "tryon" else 0,
                1 if signal_type == "save" else 0,
            ))
            if signal_type == "tryon":
                conn.execute(
                    "UPDATE nail_user_prefs_v2 SET trial_count = trial_count + 1 WHERE user_id = ?",
                    (user_id,)
                )
            elif signal_type == "save":
                conn.execute(
                    "UPDATE nail_user_prefs_v2 SET save_count = save_count + 1 WHERE user_id = ?",
                    (user_id,)
                )
            conn.commit()

    except Exception as e:
        logger.error("_update_multidim_profile failed (user=%s style=%s): %s", user_id, style_id, e)


def get_user_multidim_profile(user_id: str) -> dict | None:
    """获取用户多维度画像，推荐引擎使用。

    Returns:
        {"pref_vector": list, "color_vector": list | None, "pattern_vector": list | None,
         "style_tags": dict, "trial_count": int, "save_count": int} or None
    """
    import json as _json

    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT pref_vector, color_vector, pattern_vector, style_tags, "
                "occasion_tags, trial_count, save_count "
                "FROM nail_user_prefs_v2 WHERE user_id=?",
                (user_id,)
            ).fetchone()

        if row is None:
            # 降级到旧表
            with get_db() as conn:
                row = conn.execute(
                    "SELECT pref_vector, trial_count, save_count FROM nail_user_prefs WHERE user_id=?",
                    (user_id,)
                ).fetchone()
            if row is None:
                return None
            pref = _json.loads(row["pref_vector"])
            if len(pref) != 512:
                padded = [0.0] * 512
                padded[:min(len(pref), 512)] = pref[:min(len(pref), 512)]
                pref = padded
            return {
                "pref_vector": pref,
                "color_vector": None,
                "pattern_vector": None,
                "style_tags": {},
                "trial_count": row["trial_count"] or 0,
                "save_count": row["save_count"] or 0,
            }

        return {
            "pref_vector": _json.loads(row["pref_vector"]),
            "color_vector": _json.loads(row["color_vector"]) if row["color_vector"] else None,
            "pattern_vector": _json.loads(row["pattern_vector"]) if row["pattern_vector"] else None,
            "style_tags": _json.loads(row["style_tags"]) if row["style_tags"] else {},
            "occasion_tags": _json.loads(row["occasion_tags"]) if row["occasion_tags"] else {},
            "trial_count": row["trial_count"] or 0,
            "save_count": row["save_count"] or 0,
        }
    except Exception as e:
        logger.error("get_user_multidim_profile failed (user=%s): %s", user_id, e)
        return None
