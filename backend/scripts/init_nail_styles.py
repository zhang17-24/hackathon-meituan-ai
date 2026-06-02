#!/usr/bin/env python3
"""
冷启动脚本：将内置款式描述批量嵌入 ChromaDB nail_styles collection。
使用 Chinese-CLIP 多模态嵌入 (512d)。

用法：cd backend && uv run python scripts/init_nail_styles.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")

BUILTIN_STYLES = [
    # ── 法式 & 变体 ──
    {"style_id": "french-001", "description": "经典法式美甲，白色甲尖，粉嫩底色，干净优雅", "category": "法式", "color_tags": "white,pink", "color_group": "light", "pattern_type": "french", "image_path": ""},
    {"style_id": "french-002", "description": "斜法式美甲，对角白色甲尖线条，裸粉底色，现代感十足", "category": "法式", "color_tags": "white,nude", "color_group": "light", "pattern_type": "french", "image_path": ""},
    {"style_id": "french-003", "description": "V形法式美甲，白色V字形甲尖，透粉色底，利落干练", "category": "法式", "color_tags": "white,sheer_pink", "color_group": "light", "pattern_type": "french", "image_path": ""},
    {"style_id": "french-004", "description": "双法式线美甲，两条平行白色细线在甲尖，米白底，极简高级", "category": "法式", "color_tags": "white,cream", "color_group": "light", "pattern_type": "french", "image_path": ""},
    {"style_id": "french-005", "description": "反法式美甲，白色半月形在甲根，深粉底色，独特个性", "category": "法式", "color_tags": "white,deep_pink", "color_group": "dark", "pattern_type": "french", "image_path": ""},

    # ── 渐变 & 晕染 ──
    {"style_id": "gradient-001", "description": "渐变美甲，从深粉到浅紫的柔和过渡，梦幻少女风", "category": "渐变", "color_tags": "pink,purple", "color_group": "warm", "pattern_type": "gradient", "image_path": ""},
    {"style_id": "gradient-002", "description": "蓝白渐变，从深蓝到透白如天空海洋过渡，清新夏日感", "category": "渐变", "color_tags": "blue,white", "color_group": "cool", "pattern_type": "gradient", "image_path": ""},
    {"style_id": "gradient-003", "description": "夕阳渐变，从橙红到金黄再到淡粉，温暖落日余晖效果", "category": "渐变", "color_tags": "orange,gold,pink", "color_group": "warm", "pattern_type": "gradient", "image_path": ""},
    {"style_id": "gradient-004", "description": "裸色到酒红渐变，由浅入深的优雅过渡，成熟气质", "category": "渐变", "color_tags": "nude,burgundy", "color_group": "dark", "pattern_type": "gradient", "image_path": ""},

    # ── 纯色 ──
    {"style_id": "solid-red-001", "description": "纯色红色美甲，高饱和正红，气场十足", "category": "纯色", "color_tags": "red", "color_group": "warm", "pattern_type": "solid", "image_path": ""},
    {"style_id": "solid-nude-001", "description": "裸色美甲，接近肤色的米白，百搭日常通勤首选", "category": "纯色", "color_tags": "nude,beige", "color_group": "light", "pattern_type": "solid", "image_path": ""},
    {"style_id": "solid-blue-001", "description": "蓝色系美甲，海军蓝底色，夏日清爽感", "category": "纯色", "color_tags": "blue,navy", "color_group": "cool", "pattern_type": "solid", "image_path": ""},
    {"style_id": "solid-dark-001", "description": "暗色系美甲，深酒红色，神秘性感", "category": "纯色", "color_tags": "dark_red,burgundy", "color_group": "dark", "pattern_type": "solid", "image_path": ""},
    {"style_id": "solid-black-001", "description": "纯黑美甲，高光泽纯黑甲面，酷感十足，百搭任何穿搭", "category": "纯色", "color_tags": "black", "color_group": "dark", "pattern_type": "solid", "image_path": ""},
    {"style_id": "solid-white-001", "description": "纯白美甲，亮白甲面如一尘不染，极简干净利落", "category": "纯色", "color_tags": "white", "color_group": "light", "pattern_type": "solid", "image_path": ""},
    {"style_id": "solid-green-001", "description": "墨绿色美甲，浓郁森林绿，复古高级感", "category": "纯色", "color_tags": "dark_green,forest_green", "color_group": "dark", "pattern_type": "solid", "image_path": ""},
    {"style_id": "solid-plum-001", "description": "梅子色美甲，紫调深粉如熟透梅子，温柔有气质", "category": "纯色", "color_tags": "plum,mauve", "color_group": "dark", "pattern_type": "solid", "image_path": ""},

    # ── 花纹 & 图案 ──
    {"style_id": "floral-001", "description": "碎花美甲，白底小碎花图案，清新田园风", "category": "花纹", "color_tags": "white,green,pink", "color_group": "light", "pattern_type": "floral", "image_path": ""},
    {"style_id": "floral-002", "description": "大花朵美甲，透明底色上手绘玫瑰花图案，华丽精致", "category": "花纹", "color_tags": "red,green,clear", "color_group": "warm", "pattern_type": "floral", "image_path": ""},
    {"style_id": "cow-print-001", "description": "奶牛纹美甲，白底不规则黑色斑块，如荷斯坦奶牛花纹，活泼俏皮", "category": "花纹", "color_tags": "white,black", "color_group": "light", "pattern_type": "cow", "image_path": ""},
    {"style_id": "leopard-001", "description": "豹纹美甲，裸色底棕色不规则环形斑点，野性时尚", "category": "花纹", "color_tags": "nude,brown", "color_group": "warm", "pattern_type": "leopard", "image_path": ""},
    {"style_id": "zebra-001", "description": "斑马纹美甲，黑白相间不规则条纹，大胆醒目", "category": "花纹", "color_tags": "black,white", "color_group": "dark", "pattern_type": "stripe", "image_path": ""},
    {"style_id": "checker-001", "description": "棋盘格美甲，黑白相间方块格子图案，复古摩登", "category": "花纹", "color_tags": "black,white", "color_group": "dark", "pattern_type": "plaid", "image_path": ""},
    {"style_id": "polka-001", "description": "红底白色波点美甲，均匀圆点分布，复古甜心风", "category": "花纹", "color_tags": "red,white", "color_group": "warm", "pattern_type": "dot", "image_path": ""},
    {"style_id": "geo-line-001", "description": "几何线条美甲，裸色底细黑线构成三角形和菱形，极简现代", "category": "花纹", "color_tags": "nude,black", "color_group": "light", "pattern_type": "stripe", "image_path": ""},

    # ── 闪粉 & 亮片 ──
    {"style_id": "glitter-001", "description": "闪粉美甲，金色细闪粉均匀分布，节日感十足", "category": "闪粉", "color_tags": "gold", "color_group": "warm", "pattern_type": "glitter", "image_path": ""},
    {"style_id": "glitter-002", "description": "银色亮片美甲，透明底密布银色细闪，如星空闪烁", "category": "闪粉", "color_tags": "silver,clear", "color_group": "cool", "pattern_type": "glitter", "image_path": ""},
    {"style_id": "glitter-003", "description": "渐变闪粉美甲，从金色渐变到玫瑰金闪粉，奢华高级", "category": "闪粉", "color_tags": "gold,rose_gold", "color_group": "warm", "pattern_type": "glitter", "image_path": ""},

    # ── 大理石 & 石纹 ──
    {"style_id": "marble-001", "description": "白色大理石美甲，白底灰色有机纹路，天然石材质感", "category": "大理石", "color_tags": "white,gray", "color_group": "light", "pattern_type": "marble", "image_path": ""},
    {"style_id": "marble-002", "description": "黑色大理石美甲，黑底白色细纹如黑夜闪电，神秘高贵", "category": "大理石", "color_tags": "black,white", "color_group": "dark", "pattern_type": "marble", "image_path": ""},

    # ── 猫眼 & 镜面 ──
    {"style_id": "cat-eye-001", "description": "猫眼美甲，深绿底一道银色猫眼光带，磁石效果神秘迷人", "category": "猫眼", "color_tags": "dark_green,silver", "color_group": "dark", "pattern_type": "cat_eye", "image_path": ""},
    {"style_id": "cat-eye-002", "description": "红猫眼美甲，酒红底金色光带如猫眼石，奢华质感", "category": "猫眼", "color_tags": "burgundy,gold", "color_group": "dark", "pattern_type": "cat_eye", "image_path": ""},
    {"style_id": "chrome-001", "description": "镜面银美甲，高反射银色镜面效果，未来科技感", "category": "镜面", "color_tags": "silver,chrome", "color_group": "cool", "pattern_type": "solid", "image_path": ""},

    # ── 磨砂 & 特殊质感 ──
    {"style_id": "matte-001", "description": "磨砂黑美甲，哑光纯黑无光泽，低调暗黑风", "category": "磨砂", "color_tags": "black", "color_group": "dark", "pattern_type": "solid", "image_path": ""},
    {"style_id": "matte-002", "description": "磨砂豆沙粉美甲，哑光温柔豆沙色，知性优雅", "category": "磨砂", "color_tags": "mauve,dusty_pink", "color_group": "warm", "pattern_type": "solid", "image_path": ""},
    {"style_id": "jelly-001", "description": "果冻美甲，透明粉橘色如水蜜桃果冻，清透水润", "category": "果冻", "color_tags": "peach,coral,clear", "color_group": "warm", "pattern_type": "solid", "image_path": ""},
    {"style_id": "jelly-002", "description": "果冻蓝美甲，半透明冰蓝色如薄荷果冻，清凉夏日感", "category": "果冻", "color_tags": "ice_blue,clear", "color_group": "cool", "pattern_type": "solid", "image_path": ""},
    {"style_id": "velvet-001", "description": "丝绒美甲，深紫色绒面质感如天鹅绒，温暖复古奢华", "category": "丝绒", "color_tags": "purple,deep_violet", "color_group": "dark", "pattern_type": "solid", "image_path": ""},

    # ── 简约 & 线条 ──
    {"style_id": "minimalist-001", "description": "简约线条美甲，白底细黑线，极简现代风", "category": "简约", "color_tags": "white,black", "color_group": "light", "pattern_type": "stripe", "image_path": ""},
    {"style_id": "minimalist-002", "description": "小银点美甲，裸粉底银色小圆点在甲面中央，极简精致", "category": "简约", "color_tags": "nude,silver", "color_group": "light", "pattern_type": "dot", "image_path": ""},
    {"style_id": "minimalist-003", "description": "月牙镂空美甲，裸色底甲根半圆留白如月牙，日系简约", "category": "简约", "color_tags": "nude,white", "color_group": "light", "pattern_type": "french", "image_path": ""},

    # ── 艺术 & 抽象 ──
    {"style_id": "art-001", "description": "艺术美甲，手绘抽象图案，独一无二", "category": "艺术", "color_tags": "multicolor", "color_group": "warm", "pattern_type": "floral", "image_path": ""},
    {"style_id": "art-002", "description": "水彩晕染美甲，如中国水墨画在指甲上的渲染效果，渐变中有笔触纹理", "category": "艺术", "color_tags": "ink_black,gray,white", "color_group": "cool", "pattern_type": "marble", "image_path": ""},
    {"style_id": "art-003", "description": "波普艺术美甲，鲜艳撞色搭配大面积几何色块，如安迪沃霍尔风格", "category": "艺术", "color_tags": "red,yellow,blue,white", "color_group": "warm", "pattern_type": "plaid", "image_path": ""},

    # ── 金属 & 箔片 ──
    {"style_id": "foil-001", "description": "金箔美甲，透明底色上贴不规则金箔碎片，高级轻奢", "category": "金属", "color_tags": "gold,clear", "color_group": "warm", "pattern_type": "glitter", "image_path": ""},
    {"style_id": "foil-002", "description": "玫瑰金箔美甲，裸粉底玫瑰金箔片点缀，温柔奢华", "category": "金属", "color_tags": "rose_gold,nude_pink", "color_group": "warm", "pattern_type": "glitter", "image_path": ""},

    # ── 3D 立体 & 饰品 ──
    {"style_id": "3d-001", "description": "立体珍珠美甲，裸粉底甲根镶嵌小珍珠和微钻，精致如珠宝", "category": "3D立体", "color_tags": "nude,pearl_white", "color_group": "light", "pattern_type": "solid", "image_path": ""},
    {"style_id": "3d-002", "description": "蝴蝶结立体美甲，透明粉底甲面上立体树脂蝴蝶结，甜美可爱", "category": "3D立体", "color_tags": "pink,clear", "color_group": "warm", "pattern_type": "solid", "image_path": ""},

    # ── 韩系 & 日系风格 ──
    {"style_id": "korean-001", "description": "韩系玻璃美甲，清透裸粉底高亮光泽如玻璃面，自然精致", "category": "韩系", "color_tags": "nude_pink,clear", "color_group": "light", "pattern_type": "solid", "image_path": ""},
    {"style_id": "korean-002", "description": "韩系晕染美甲，牛奶白底淡粉晕染如花瓣融入，温柔似水", "category": "韩系", "color_tags": "milky_white,pink", "color_group": "light", "pattern_type": "gradient", "image_path": ""},
    {"style_id": "japanese-001", "description": "日系干花美甲，透明底嵌入真实干花碎片，自然清新文艺", "category": "日系", "color_tags": "clear,floral_multicolor", "color_group": "light", "pattern_type": "floral", "image_path": ""},

    # ── 节日 & 主题 ──
    {"style_id": "festive-001", "description": "新年红金美甲，正红底金色细闪和金色线条装饰，喜庆节日款", "category": "节日", "color_tags": "red,gold", "color_group": "warm", "pattern_type": "glitter", "image_path": ""},
    {"style_id": "bridal-001", "description": "新娘美甲，裸粉底白色蕾丝花纹和珍珠点缀，精致纯洁", "category": "新娘", "color_tags": "nude,white,pearl", "color_group": "light", "pattern_type": "floral", "image_path": ""},
]

# ── 颜色组映射 ──
_COLOR_GROUP_MAP = {
    "light": ["white", "nude", "beige", "cream", "pink", "light_pink", "nude_pink", "clear", "sheer_pink", "milky_white", "pearl_white", "ice_blue"],
    "dark": ["black", "navy", "burgundy", "dark_green", "dark_red", "deep_violet", "deep_pink", "ink_black", "plum", "forest_green"],
    "warm": ["red", "orange", "gold", "pink", "coral", "peach", "rose_gold", "brown", "mauve", "dusty_pink", "yellow"],
    "cool": ["blue", "purple", "silver", "gray", "green", "chrome", "ice_blue"],
}


def _find_style_image(style: dict) -> str:
    explicit = style.get("image_path", "")
    if explicit and Path(explicit).exists():
        return explicit

    style_id = style["style_id"]
    search_dirs = [
        Path("data/styles"),
        Path("data/uploads/styles"),
    ]
    search_exts = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

    for base_dir in search_dirs:
        for ext in search_exts:
            candidate = base_dir / f"{style_id}{ext}"
            if candidate.exists():
                return str(candidate)

    return ""


def _build_style_text(style: dict) -> str:
    parts = [style["description"]]
    if style.get("category"):
        parts.append(f"风格分类：{style['category']}")
    if style.get("color_tags"):
        parts.append(f"颜色标签：{style['color_tags'].replace(',', '、')}")
    if style.get("pattern_type"):
        parts.append(f"图案类型：{style['pattern_type']}")
    if style.get("color_group"):
        parts.append(f"综合色系：{style['color_group']}")
    return "。".join(parts)


def main():
    import chromadb
    from packages.harness.deerflow.tools.nail.base import get_db, init_nail_tables
    from packages.harness.deerflow.tools.nail.embedding import fused_style_embedding

    print(f"初始化 ChromaDB nail_styles collection at {CHROMA_DIR}")
    print("使用 Chinese-CLIP 多模态嵌入 (512d)，优先融合真实款式图")

    init_nail_tables()
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # 删除旧 collection
    try:
        client.delete_collection("nail_styles")
        print("已删除旧 collection")
    except Exception:
        pass

    print(f"正在构建 {len(BUILTIN_STYLES)} 条款式的多模态 embedding...")
    descriptions = []
    embeddings = []
    metadatas = []
    ids = []

    with get_db() as conn:
        for style in BUILTIN_STYLES:
            style_image_path = _find_style_image(style)
            style_text = _build_style_text(style)
            embedding = fused_style_embedding(
                image_path=style_image_path or None,
                text_desc=style_text,
                weights=(0.7, 0.25, 0.05),
            )
            if embedding is None:
                print(f"跳过无法编码的款式: {style['style_id']}")
                continue

            descriptions.append(style["description"])
            embeddings.append(embedding.tolist())
            ids.append(style["style_id"])
            metadatas.append({
                "style_id": style["style_id"],
                "category": style.get("category", ""),
                "color_tags": style.get("color_tags", ""),
                "color_group": style.get("color_group", ""),
                "pattern_type": style.get("pattern_type", ""),
                "image_path": style_image_path,
                "source": "static",
                "embedding_strategy": "image_text_fused" if style_image_path else "text_only",
            })

            conn.execute(
                """
                INSERT INTO nail_style_catalog
                    (style_id, description, category, color_tags, image_path, source, color_group, pattern_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                    style["style_id"],
                    style["description"],
                    style.get("category", ""),
                    style.get("color_tags", ""),
                    style_image_path,
                    "static",
                    style.get("color_group", ""),
                    style.get("pattern_type", ""),
                ),
            )
        conn.commit()

    # 创建 collection (不带 embedding_function, 手动传嵌入)
    print("创建新 collection (Chinese-CLIP 512d, cosine)...")
    col = client.create_collection(
        "nail_styles",
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )

    # 批量导入（传预计算嵌入）
    col.add(
        embeddings=embeddings,
        documents=descriptions,
        metadatas=metadatas,
        ids=ids,
    )

    dim = len(embeddings[0]) if embeddings else 0
    image_count = sum(1 for meta in metadatas if meta["image_path"])
    print(f"成功导入 {len(ids)} 个款式，其中 {image_count} 个使用真实图片融合")
    print(f"嵌入维度: {dim}d (Chinese-CLIP)")
    print(f"HNSW 距离: cosine")


if __name__ == "__main__":
    main()
