#!/usr/bin/env python3
"""把打过标签的 Commons 款式图追加进 Chroma nail_styles + nail_style_catalog。

用法：cd backend && uv run python scripts/ingest_tagged_styles.py

注意：只追加不重建（保留 init_nail_styles.py 的 53 款）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb

from packages.harness.nailflow.tools.nail.base import DB_PATH, get_db, init_nail_tables
from packages.harness.nailflow.tools.nail.embedding import fused_style_embedding

COMMONS_DIR = Path("data/styles/commons")
CHROMA_DIR = "data/chroma"


def main():
    tag_path = COMMONS_DIR / "tagged_styles.json"
    if not tag_path.exists():
        print("tagged_styles.json 不存在，请先运行 tag_commons_styles.py")
        return
    items = json.loads(tag_path.read_text(encoding="utf-8"))
    print(f"待入库款式: {len(items)}")

    init_nail_tables()
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_or_create_collection("nail_styles", embedding_function=None)

    # 已存在的 id（避免重复）
    existing = set()
    if col.count() > 0:
        existing = set(col.get(include=[])["ids"])
    print(f"collection 现有 {len(existing)} 条")

    new_ids = []
    new_embeddings = []
    new_docs = []
    new_metadatas = []

    with get_db() as conn:
        for item in items:
            sid = item["style_id"]
            img_path = item["image_path"]
            if not Path(img_path).exists():
                print(f"  跳过缺文件: {sid} ({img_path})")
                continue

            vec = fused_style_embedding(
                image_path=img_path,
                text_desc=item["description"],
                weights=(0.7, 0.25, 0.05),
            )
            if vec is None:
                print(f"  编码失败: {sid}")
                continue

            new_ids.append(sid)
            new_embeddings.append(vec.tolist())
            new_docs.append(item["description"])
            new_metadatas.append({
                "style_id": sid,
                "category": item.get("category", "通用"),
                "color_tags": item.get("color_tags", ""),
                "color_group": item.get("color_group", ""),
                "pattern_type": item.get("pattern_type", ""),
                "image_path": img_path,
                "source": "commons",
                "embedding_strategy": "image_text_fused",
                "source_url": item.get("source_url", ""),
                "license": item.get("license", ""),
            })

            conn.execute(
                """
                INSERT INTO nail_style_catalog
                    (style_id, description, category, color_tags, image_path, source, color_group, pattern_type)
                VALUES (?, ?, ?, ?, ?, 'commons', ?, ?)
                ON CONFLICT(style_id) DO UPDATE SET
                    description = excluded.description,
                    category = excluded.category,
                    color_tags = excluded.color_tags,
                    image_path = excluded.image_path,
                    source = excluded.source,
                    color_group = excluded.color_group,
                    pattern_type = excluded.pattern_type
                """,
                (
                    sid,
                    item["description"],
                    item.get("category", "通用"),
                    item.get("color_tags", ""),
                    img_path,
                    item.get("color_group", ""),
                    item.get("pattern_type", ""),
                ),
            )
        conn.commit()

    if new_ids:
        # upsert：新 id 追加，已存在的 id 更新嵌入（例如修复 image_path）
        col.upsert(
            embeddings=new_embeddings,
            documents=new_docs,
            metadatas=new_metadatas,
            ids=new_ids,
        )

    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM nail_style_catalog").fetchone()[0]
        with_img = conn.execute(
            "SELECT COUNT(*) FROM nail_style_catalog WHERE image_path IS NOT NULL AND image_path != ''"
        ).fetchone()[0]

    print(f"新增 {len(new_ids)} 款，Chroma 总数 {col.count()}，catalog {total} 行（{with_img} 带图）")
    print(f"DB: {DB_PATH}")


if __name__ == "__main__":
    main()
