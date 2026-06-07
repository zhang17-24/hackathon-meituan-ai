#!/usr/bin/env python3
"""Backfill static styles from Chroma into SQLite nail_style_catalog."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
SQLITE_PATH = Path("data/nailflow.db")

from packages.harness.nailflow.tools.nail.base import init_nail_tables  # noqa: E402
from scripts.init_nail_styles import BUILTIN_STYLES  # noqa: E402


BUILTIN_STYLE_MAP = {style["style_id"]: style for style in BUILTIN_STYLES}


def _fetch_chroma_static_styles() -> list[dict]:
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_or_create_collection("nail_styles", embedding_function=None)
    payload = col.get(include=["metadatas", "documents"])

    records = []
    for style_id, meta, doc in zip(
        payload.get("ids", []),
        payload.get("metadatas", []),
        payload.get("documents", []),
    ):
        meta = meta or {}
        if meta.get("source") != "static":
            continue
        records.append({
            "style_id": style_id,
            "description": doc or "",
            "category": meta.get("category", ""),
            "color_group": meta.get("color_group", ""),
            "pattern_type": meta.get("pattern_type", ""),
            "image_path": meta.get("image_path", ""),
            "source": meta.get("source", "static"),
        })
    return records


def migrate_static_styles() -> dict:
    init_nail_tables()

    chroma_styles = _fetch_chroma_static_styles()
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(f"SQLite 数据库不存在: {SQLITE_PATH}")

    inserted = 0
    updated = 0
    skipped = 0
    migrated_ids: list[str] = []

    conn = sqlite3.connect(SQLITE_PATH)
    try:
        for row in chroma_styles:
            style_id = row["style_id"]
            builtin = BUILTIN_STYLE_MAP.get(style_id, {})
            color_tags = builtin.get("color_tags", "")
            description = builtin.get("description") or row["description"] or style_id
            category = builtin.get("category") or row["category"]
            image_path = builtin.get("image_path") or row["image_path"] or ""
            color_group = builtin.get("color_group") or row["color_group"]
            pattern_type = builtin.get("pattern_type") or row["pattern_type"]
            source = "static"

            existing = conn.execute(
                "SELECT style_id, source FROM nail_style_catalog WHERE style_id=?",
                (style_id,),
            ).fetchone()

            conn.execute(
                """
                INSERT INTO nail_style_catalog
                    (style_id, description, category, color_tags, image_path, source, color_group, pattern_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(style_id) DO UPDATE SET
                    description=excluded.description,
                    category=excluded.category,
                    color_tags=excluded.color_tags,
                    image_path=excluded.image_path,
                    source=excluded.source,
                    color_group=excluded.color_group,
                    pattern_type=excluded.pattern_type
                """,
                (
                    style_id,
                    description,
                    category,
                    color_tags,
                    image_path,
                    source,
                    color_group,
                    pattern_type,
                ),
            )

            if existing is None:
                inserted += 1
                migrated_ids.append(style_id)
            elif existing[1] != "static":
                updated += 1
                migrated_ids.append(style_id)
            else:
                skipped += 1

        conn.commit()
    finally:
        conn.close()

    return {
        "chroma_static_count": len(chroma_styles),
        "inserted": inserted,
        "updated": updated,
        "skipped_existing_static": skipped,
        "migrated_sample": migrated_ids[:20],
    }


def main() -> None:
    result = migrate_static_styles()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
