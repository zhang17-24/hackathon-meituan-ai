#!/usr/bin/env python3
"""为抓取的 Commons 美甲图打款式标签：CLIP 编码 + 与内置款式文本匹配。

用法：cd backend && uv run python scripts/tag_commons_styles.py

输出：data/styles/commons/tagged_styles.json
    [{"style_id", "image_path", "description", "category", "color_tags",
      "color_group", "pattern_type", "similarity", "source_url"}]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from packages.harness.nailflow.tools.nail.embedding import encode_image, encode_text

COMMONS_DIR = Path("data/styles/commons")
MIN_SIM_THRESHOLD = 0.50  # 低于此相似度的图不绑定具体类别，归为"通用美甲"
BUILTIN_TEXTS = {  # 与 init_nail_styles.py 一致的款式描述（做弱标签锚点）
    "french-001": "经典法式美甲，白色甲尖，粉嫩底色",
    "french-002": "斜法式美甲，对角白色甲尖线条，裸粉底色",
    "french-003": "V形法式美甲，白色V字形甲尖，透粉色底",
    "french-004": "双法式线美甲，两条平行白色细线在甲尖，米白底",
    "french-005": "反法式美甲，白色半月形在甲根，深粉底色",
    "gradient-001": "渐变美甲，从深粉到浅紫的柔和过渡，梦幻少女风",
    "gradient-002": "蓝白渐变美甲，从深蓝到透白，清新夏日感",
    "gradient-003": "夕阳渐变美甲，从橙红到金黄再到淡粉，落日效果",
    "gradient-004": "裸色到酒红渐变美甲，优雅过渡，成熟气质",
    "solid-red-001": "纯色红色美甲，高饱和正红",
    "solid-nude-001": "裸色美甲，接近肤色的米白，百搭通勤",
    "solid-blue-001": "蓝色系美甲，海军蓝底色，夏日清爽",
    "solid-dark-001": "暗色系美甲，深酒红色，神秘性感",
    "solid-black-001": "纯黑美甲，高光泽纯黑甲面，酷感十足",
    "solid-white-001": "纯白美甲，亮白甲面，极简干净",
    "solid-green-001": "墨绿色美甲，浓郁森林绿，复古高级感",
    "solid-plum-001": "梅子色美甲，紫调深粉，温柔有气质",
    "floral-001": "碎花美甲，白底小碎花图案，清新田园风",
    "floral-002": "大花朵美甲，透明底手绘玫瑰花图案，华丽精致",
    "cow-print-001": "奶牛纹美甲，白底不规则黑色斑块，活泼俏皮",
    "leopard-001": "豹纹美甲，裸色底棕色不规则环形斑点，野性时尚",
    "zebra-001": "斑马纹美甲，黑白相间不规则条纹",
    "checker-001": "棋盘格美甲，黑白相间方块格子，复古摩登",
    "polka-001": "红底白色波点美甲，均匀圆点分布，复古甜心",
    "geo-line-001": "几何线条美甲，裸色底细黑线构成三角形和菱形，极简现代",
    "glitter-001": "闪粉美甲，金色细闪粉均匀分布，节日感",
    "glitter-002": "银色亮片美甲，透明底密布银色细闪，如星空",
    "glitter-003": "渐变闪粉美甲，从金色渐变到玫瑰金闪粉，奢华",
    "marble-001": "白色大理石美甲，白底灰色有机纹路，天然石材感",
    "marble-002": "黑色大理石美甲，黑底白色细纹，神秘高贵",
    "cat-eye-001": "猫眼美甲，深绿底一道银色猫眼光带，磁石效果",
    "cat-eye-002": "红猫眼美甲，酒红底金色光带如猫眼石，奢华",
    "chrome-001": "镜面银美甲，高反射银色镜面效果，未来科技感",
    "matte-001": "磨砂黑美甲，哑光纯黑无光泽，低调暗黑",
    "matte-002": "磨砂豆沙粉美甲，哑光温柔豆沙色，知性优雅",
    "jelly-001": "果冻美甲，透明粉橘色如水蜜桃果冻，清透水润",
    "jelly-002": "果冻蓝美甲，半透明冰蓝色如薄荷果冻，清凉",
    "velvet-001": "丝绒美甲，深紫色绒面质感如天鹅绒，复古奢华",
    "minimalist-001": "简约线条美甲，白底细黑线，极简现代",
    "minimalist-002": "小银点美甲，裸粉底银色小圆点，极简精致",
    "minimalist-003": "月牙镂空美甲，裸色底甲根半圆留白如月牙，日系简约",
    "art-001": "艺术美甲，手绘抽象图案，独一无二",
    "art-002": "水彩晕染美甲，如中国水墨画渲染效果",
    "art-003": "波普艺术美甲，鲜艳撞色几何色块，安迪沃霍尔风格",
    "foil-001": "金箔美甲，透明底色贴不规则金箔碎片，高级轻奢",
    "foil-002": "玫瑰金箔美甲，裸粉底玫瑰金箔片点缀，温柔奢华",
    "3d-001": "立体珍珠美甲，裸粉底镶嵌小珍珠和微钻，精致如珠宝",
    "3d-002": "蝴蝶结立体美甲，透明粉底立体树脂蝴蝶结，甜美可爱",
    "korean-001": "韩系玻璃美甲，清透裸粉底高亮光泽如玻璃面",
    "korean-002": "韩系晕染美甲，牛奶白底淡粉晕染如花瓣融入",
    "japanese-001": "日系干花美甲，透明底嵌入真实干花碎片，文艺",
    "festive-001": "新年红金美甲，正红底金色细闪和线条装饰，喜庆",
    "bridal-001": "新娘美甲，裸粉底白色蕾丝花纹和珍珠点缀，精致纯洁",
}


def _clean_style_id(title: str) -> str:
    import hashlib

    stem = Path(title).stem
    stem = re.sub(r"[^a-zA-Z0-9_-]", "-", stem)
    stem = re.sub(r"-+", "-", stem).strip("-")
    if stem:
        return stem[:60]
    # 纯非 ASCII 文件名 → 用 hash 保证唯一
    return hashlib.md5(title.encode("utf-8")).hexdigest()[:16]


# 文件名关键词 → (category, color_group, pattern_type)
_TITLE_KEYWORD_MAP: list[tuple[str, str, str, str]] = [
    ("french", "法式", "light", "french"),
    ("ombre", "渐变", "warm", "gradient"),
    ("gradient", "渐变", "", "gradient"),
    ("fade", "渐变", "", "gradient"),
    ("cat eye", "猫眼", "dark", "cat_eye"),
    ("cat-eye", "猫眼", "dark", "cat_eye"),
    ("jelly", "果冻", "light", "jelly"),
    ("matte", "磨砂", "", "solid"),
    ("velvet", "丝绒", "dark", "solid"),
    ("floral", "花纹", "", "floral"),
    ("flower", "花纹", "", "floral"),
    ("cherry", "花纹", "", "floral"),
    ("leopard", "花纹", "warm", "leopard"),
    ("animal", "花纹", "", "leopard"),
    ("zebra", "花纹", "dark", "stripe"),
    ("checker", "花纹", "dark", "plaid"),
    ("polka", "花纹", "warm", "dot"),
    ("geometric", "简约", "light", "stripe"),
    ("marble", "大理石", "", "marble"),
    ("glitter", "闪粉", "", "glitter"),
    ("diamond", "闪粉", "", "glitter"),
    ("holo", "闪粉", "", "glitter"),
    ("gold", "闪粉", "warm", "glitter"),
    ("silver", "闪粉", "cool", "glitter"),
    ("chrome", "镜面", "cool", "solid"),
    ("mirror", "镜面", "cool", "solid"),
    ("acrylic", "纯色", "", "solid"),
    ("red", "纯色", "warm", "solid"),
    ("pink", "纯色", "warm", "solid"),
    ("blue", "纯色", "cool", "solid"),
    ("black", "纯色", "dark", "solid"),
    ("white", "纯色", "light", "solid"),
    ("nude", "纯色", "light", "solid"),
    ("purple", "纯色", "dark", "solid"),
    ("green", "纯色", "dark", "solid"),
    ("manicure", "通用", "", ""),
    ("nail art", "通用", "", ""),
]


def _title_hint(title: str) -> tuple[str, str, str]:
    low = title.lower()
    for keyword, category, color_group, pattern_type in _TITLE_KEYWORD_MAP:
        if keyword in low:
            return category, color_group, pattern_type
    return "通用", "", ""


def main():
    manifest_path = COMMONS_DIR / "bulk_manifest.json"
    if not manifest_path.exists():
        print("manifest 不存在，请先运行 bulk_fetch_style_images.py")
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    downloaded = [r for r in manifest["images"] if r.get("downloaded")]
    print(f"已下载 {len(downloaded)} 张，开始编码与标签匹配...")

    # 内置款式文本向量
    ids = list(BUILTIN_TEXTS)
    txt_mat = encode_text([BUILTIN_TEXTS[i] for i in ids])
    txt_norm = txt_mat / np.linalg.norm(txt_mat, axis=1, keepdims=True)

    tagged = []
    skipped_broken = 0
    low_sim = 0

    for rec in downloaded:
        path = Path(rec["local_path"])
        if not path.exists():
            skipped_broken += 1
            continue
        try:
            from PIL import Image

            with Image.open(path) as im:
                im.verify()
        except Exception:  # noqa: BLE001
            skipped_broken += 1
            continue

        vec = encode_image(str(path))
        if vec is None:
            skipped_broken += 1
            continue

        sims = txt_norm @ (vec / np.linalg.norm(vec))
        best = int(np.argmax(sims))
        top1_id, top1_sim = ids[best], float(sims[best])

        # 类别标签：文件名关键词优先（可靠），CLIP 弱匹配兜底
        title_category, title_color, title_pattern = _title_hint(rec["title"])
        if title_category != "通用" or top1_sim >= MIN_SIM_THRESHOLD:
            if title_category == "通用":
                anchor = BUILTIN_TEXTS[top1_id]
                title_category = anchor.split("美甲")[0].split("，")[0]
                title_color = {
                    "french": "light", "gradient": "warm", "cat_eye": "dark",
                    "marble": "light", "glitter": "warm", "solid": "light",
                }.get(rec.get("pattern_type", ""), "")
                title_pattern = rec.get("pattern_type", "")
            description = f"{title_category}风格美甲，来自网络公开图库"
        else:
            description = "美甲款式图片，来自网络公开图库"
            low_sim += 1

        # 存相对路径（与内置款式 data/styles/xxx.jpg 一致），避免绝对路径进向量库
        try:
            rel_path = str(path.relative_to(Path.cwd()))
        except ValueError:
            rel_path = str(path)
        tagged.append({
            "style_id": f"wm-{_clean_style_id(rec['title'])}",
            "image_path": rel_path,
            "description": description,
            "category": title_category,
            "color_tags": "",
            "color_group": title_color,
            "pattern_type": title_pattern,
            "similarity": round(top1_sim, 3),
            "source_url": rec.get("source_url", ""),
            "license": rec.get("license_short_name", ""),
        })

    out = COMMONS_DIR / "tagged_styles.json"
    out.write_text(json.dumps(tagged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成: 打标 {len(tagged)} 张 (跳过损坏 {skipped_broken}, 低相似度归通用 {low_sim})")
    print(f"输出: {out}")


if __name__ == "__main__":
    main()
