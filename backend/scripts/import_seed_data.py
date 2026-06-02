#!/usr/bin/env python3
"""
种子数据导入脚本：将抓取的专业美甲知识和款式图片注入 SQLite 和 ChromaDB。
支持增量导入。

用法：cd backend && uv run python scripts/import_seed_data.py
"""

import json
import logging
import os
import sys
from pathlib import Path

# 设置项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.harness.deerflow.tools.nail.base import get_db, init_nail_tables
from packages.harness.deerflow.tools.nail.embedding import encode_text, fused_style_embedding

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
KNOWLEDGE_SEED_PATH = Path("data/knowledge/nail_knowledge_seed.json")
IMAGE_SEED_PATH = Path("data/seed_images/commons/commons_nail_images.json")

def import_knowledge(client):
    if not KNOWLEDGE_SEED_PATH.exists():
        logger.warning(f"知识种子文件不存在: {KNOWLEDGE_SEED_PATH}")
        return

    logger.info(f"开始导入知识库: {KNOWLEDGE_SEED_PATH}")
    with open(KNOWLEDGE_SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    collection = client.get_or_create_collection("nail_knowledge")
    
    with get_db() as conn:
        for topic in data.get("topics", []):
            topic_id = topic["topic_id"]
            title = topic["title"]
            summary = topic["summary"]
            points = topic["points"]
            tags = ",".join(topic.get("tags", []))
            source = json.dumps(topic.get("sources", []))
            full_content = "\n".join(points)
            
            # 1. 写入 SQLite
            conn.execute(
                """
                INSERT INTO nail_knowledge (topic_id, title, summary, content, tags, source)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic_id) DO UPDATE SET
                    title=excluded.title,
                    summary=excluded.summary,
                    content=excluded.content,
                    tags=excluded.tags,
                    source=excluded.source
                """,
                (topic_id, title, summary, full_content, tags, source)
            )
            conn.commit()
            
            # 2. 写入 ChromaDB (向量化)
            # 我们将 summary + content 组合作为检索文本
            text_to_embed = f"主题：{title}\n摘要：{summary}\n详情：{full_content}\n标签：{tags}"
            embedding = encode_text([text_to_embed])[0]
            
            collection.upsert(
                ids=[topic_id],
                embeddings=[embedding.tolist()],
                metadatas=[{
                    "type": "knowledge",
                    "topic_id": topic_id,
                    "title": title,
                    "tags": tags
                }],
                documents=[text_to_embed]
            )
            logger.info(f"  - 导入知识主题: {title}")
    
    logger.info("知识库导入完成")

def import_images(client):
    if not IMAGE_SEED_PATH.exists():
        logger.warning(f"款式图清单不存在: {IMAGE_SEED_PATH}")
        return

    logger.info(f"开始导入美甲款式图: {IMAGE_SEED_PATH}")
    with open(IMAGE_SEED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    collection = client.get_or_create_collection("nail_styles")
    
    with get_db() as conn:
        for img in data.get("images", []):
            if not img.get("downloaded"):
                logger.warning(f"  - 跳过未下载图片: {img['title']}")
                continue
            
            local_path = img.get("local_path")
            if not local_path or not Path(local_path).exists():
                logger.warning(f"  - 图片文件缺失: {img['title']} at {local_path}")
                continue

            style_id = f"commons-{img['title'].split('.')[0]}"
            description = img.get("image_description") or img.get("notes") or img["title"]
            category = img.get("style_hint", "general")
            color_group = img.get("color_group", "mixed")
            pattern_type = img.get("pattern_type", "plain")
            
            # 构建富文本描述
            rich_desc = f"{description}。风格：{category}。色系：{color_group}。图案：{pattern_type}。"
            
            # 1. 写入 SQLite
            conn.execute(
                """
                INSERT INTO nail_style_catalog 
                    (style_id, description, category, color_tags, image_path, source, color_group, pattern_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(style_id) DO UPDATE SET
                    description=excluded.description,
                    category=excluded.category,
                    image_path=excluded.image_path,
                    color_group=excluded.color_group,
                    pattern_type=excluded.pattern_type
                """,
                (style_id, rich_desc, category, "", str(local_path), "wikimedia", color_group, pattern_type)
            )
            conn.commit()
            
            # 2. 多模态 Embedding (包含降噪策略)
            logger.info(f"  - 正在为图片生成降噪 Embedding: {img['title']}")
            embedding = fused_style_embedding(
                image_path=str(local_path),
                text_desc=rich_desc,
                weights=(0.7, 0.3, 0.0) # 视觉 70%, 语义 30%
            )
            
            if embedding is not None:
                collection.upsert(
                    ids=[style_id],
                    embeddings=[embedding.tolist()],
                    metadatas=[{
                        "style_id": style_id,
                        "category": category,
                        "color_group": color_group,
                        "pattern_type": pattern_type,
                        "source": "wikimedia",
                        "image_path": str(local_path)
                    }],
                    documents=[rich_desc]
                )
                logger.info(f"  - 导入款式图完成: {style_id}")
            else:
                logger.error(f"  - 无法生成款式图 Embedding: {style_id}")

    logger.info("款式图导入完成")

def main():
    import chromadb
    
    # 确保基础目录存在
    Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
    
    # 初始化表
    init_nail_tables()
    
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    
    import_knowledge(client)
    import_images(client)
    
    print("\n" + "="*50)
    print("✅ 数据注入成功！")
    print(f"   - 知识库 (ChromaDB): nail_knowledge")
    print(f"   - 款式库 (ChromaDB): nail_styles")
    print(f"   - SQLite 记录已更新")
    print("="*50)

if __name__ == "__main__":
    main()
