#!/usr/bin/env python3
"""
冷启动脚本：将内置款式描述批量嵌入 ChromaDB nail_styles collection。
用法：cd backend && uv run python scripts/init_nail_styles.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent.parent))  # 项目根目录

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")

BUILTIN_STYLES = [
    {"style_id": "french-001", "description": "经典法式美甲，白色甲尖，粉嫩底色，干净优雅", "category": "法式", "color_tags": "white,pink", "image_path": ""},
    {"style_id": "gradient-001", "description": "渐变美甲，从深粉到浅紫的柔和过渡，梦幻少女风", "category": "渐变", "color_tags": "pink,purple", "image_path": ""},
    {"style_id": "solid-red-001", "description": "纯色红色美甲，高饱和正红，气场十足", "category": "纯色", "color_tags": "red", "image_path": ""},
    {"style_id": "floral-001", "description": "碎花美甲，白底小碎花图案，清新田园风", "category": "花纹", "color_tags": "white,green,pink", "image_path": ""},
    {"style_id": "glitter-001", "description": "闪粉美甲，金色细闪粉，节日感十足", "category": "闪粉", "color_tags": "gold", "image_path": ""},
    {"style_id": "minimalist-001", "description": "简约线条美甲，白底细黑线，极简现代风", "category": "简约", "color_tags": "white,black", "image_path": ""},
    {"style_id": "dark-001", "description": "暗色系美甲，深酒红色，神秘性感", "category": "暗色", "color_tags": "dark_red,burgundy", "image_path": ""},
    {"style_id": "nude-001", "description": "裸色美甲，接近肤色的米白，百搭日常", "category": "裸色", "color_tags": "nude,beige", "image_path": ""},
    {"style_id": "blue-001", "description": "蓝色系美甲，海军蓝底色，夏日清爽感", "category": "纯色", "color_tags": "blue,navy", "image_path": ""},
    {"style_id": "art-001", "description": "艺术美甲，手绘抽象图案，独一无二", "category": "艺术", "color_tags": "multicolor", "image_path": ""},
]


def main():
    import chromadb
    from chromadb.utils import embedding_functions

    print(f"初始化 ChromaDB nail_styles collection at {CHROMA_DIR}")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    ef = embedding_functions.DefaultEmbeddingFunction()
    col = client.get_or_create_collection("nail_styles", embedding_function=ef)

    existing_ids = set(col.get(ids=[s["style_id"] for s in BUILTIN_STYLES])["ids"])
    to_add = [s for s in BUILTIN_STYLES if s["style_id"] not in existing_ids]

    if not to_add:
        print(f"所有 {len(BUILTIN_STYLES)} 个款式已存在，无需重新导入（总计 {col.count()} 个）")
        return

    col.add(
        documents=[s["description"] for s in to_add],
        metadatas=[{
            "style_id":   s["style_id"],
            "category":   s.get("category", ""),
            "color_tags": s.get("color_tags", ""),
            "image_path": s.get("image_path", ""),
            "source":     "static",
        } for s in to_add],
        ids=[s["style_id"] for s in to_add],
    )
    print(f"✅ 成功导入 {len(to_add)} 个款式（总计 {col.count()} 个）")


if __name__ == "__main__":
    main()
