#!/usr/bin/env python3
"""Audit SQLite and Chroma consistency for nailflow indexes.

Outputs:
- data/audit/nail_index_audit.json
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from pathlib import Path


CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
SQLITE_PATH = Path("data/nailflow.db")
AUDIT_OUTPUT_PATH = Path("data/audit/nail_index_audit.json")


def _fetch_sqlite_rows() -> dict:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        style_rows = conn.execute(
            "SELECT style_id, source, image_path, category, color_group, pattern_type FROM nail_style_catalog"
        ).fetchall()
        knowledge_rows = conn.execute(
            "SELECT topic_id, title, tags, source FROM nail_knowledge"
        ).fetchall()
    finally:
        conn.close()

    return {
        "styles": [dict(row) for row in style_rows],
        "knowledge": [dict(row) for row in knowledge_rows],
    }


def _fetch_chroma_rows() -> dict:
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    style_col = client.get_or_create_collection("nail_styles", embedding_function=None)
    knowledge_col = client.get_or_create_collection("nail_knowledge", embedding_function=None)

    style_rows = style_col.get(include=["metadatas"])
    knowledge_rows = knowledge_col.get(include=["metadatas"])

    return {
        "styles": [
            {"id": style_id, **(meta or {})}
            for style_id, meta in zip(style_rows.get("ids", []), style_rows.get("metadatas", []))
        ],
        "knowledge": [
            {"id": chunk_id, **(meta or {})}
            for chunk_id, meta in zip(knowledge_rows.get("ids", []), knowledge_rows.get("metadatas", []))
        ],
    }


def _build_style_audit(sqlite_rows: list[dict], chroma_rows: list[dict]) -> dict:
    sqlite_ids = {row["style_id"] for row in sqlite_rows}
    chroma_ids = {row["id"] for row in chroma_rows}

    sqlite_source_counts = Counter((row.get("source") or "unknown") for row in sqlite_rows)
    chroma_source_counts = Counter((row.get("source") or "unknown") for row in chroma_rows)

    only_in_sqlite = sorted(sqlite_ids - chroma_ids)
    only_in_chroma = sorted(chroma_ids - sqlite_ids)
    shared = sorted(sqlite_ids & chroma_ids)

    return {
        "sqlite_count": len(sqlite_ids),
        "chroma_count": len(chroma_ids),
        "shared_count": len(shared),
        "only_in_sqlite_count": len(only_in_sqlite),
        "only_in_chroma_count": len(only_in_chroma),
        "sqlite_source_counts": dict(sqlite_source_counts),
        "chroma_source_counts": dict(chroma_source_counts),
        "only_in_sqlite_sample": only_in_sqlite[:20],
        "only_in_chroma_sample": only_in_chroma[:20],
    }


def _build_knowledge_audit(sqlite_rows: list[dict], chroma_rows: list[dict]) -> dict:
    sqlite_topic_ids = {row["topic_id"] for row in sqlite_rows}
    chroma_topic_ids = {row.get("topic_id", "") for row in chroma_rows if row.get("topic_id")}
    chunk_types = Counter((row.get("chunk_type") or "unknown") for row in chroma_rows)

    sqlite_titles_sample = sorted(row["title"] for row in sqlite_rows)[:20]
    chroma_topic_sample = sorted(chroma_topic_ids)[:20]

    return {
        "sqlite_document_count": len(sqlite_topic_ids),
        "chroma_chunk_count": len(chroma_rows),
        "chroma_topic_count": len(chroma_topic_ids),
        "sqlite_topic_sample": sqlite_titles_sample,
        "chroma_topic_sample": chroma_topic_sample,
        "chunk_type_counts": dict(chunk_types),
    }


def run_audit() -> dict:
    AUDIT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    sqlite_data = _fetch_sqlite_rows()
    chroma_data = _fetch_chroma_rows()

    report = {
        "version": "2026-06-03",
        "paths": {
            "sqlite": str(SQLITE_PATH),
            "chroma": CHROMA_DIR,
        },
        "style_audit": _build_style_audit(
            sqlite_rows=sqlite_data["styles"],
            chroma_rows=chroma_data["styles"],
        ),
        "knowledge_audit": _build_knowledge_audit(
            sqlite_rows=sqlite_data["knowledge"],
            chroma_rows=chroma_data["knowledge"],
        ),
    }
    AUDIT_OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    report = run_audit()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
