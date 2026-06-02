#!/usr/bin/env python3
"""Fetch seed nail knowledge and openly licensed nail images.

Outputs:
- data/knowledge/nail_knowledge_seed.json
- data/knowledge/nail_knowledge_seed.md
- data/seed_images/commons/commons_nail_images.json
- data/seed_images/commons/<downloaded image files>
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"
COMMONS_DIR = BASE_DIR / "data" / "seed_images" / "commons"

COMMONS_FILES = [
    {
        "title": "Polished_purple_nails_with_nail_art_on.jpg",
        "style_hint": "floral",
        "color_group": "cool",
        "pattern_type": "floral",
        "notes": "purple base with flower-themed nail art",
    },
    {
        "title": "French_Manicure_with_Glitter_nail_art_on_ring_finger.jpg",
        "style_hint": "french_glitter",
        "color_group": "light",
        "pattern_type": "french",
        "notes": "french manicure with glitter accent finger",
    },
    {
        "title": "Acrylic_nail_art_with_crystal.jpg",
        "style_hint": "3d_crystal",
        "color_group": "light",
        "pattern_type": "solid",
        "notes": "acrylic nails with crystal decoration",
    },
    {
        "title": "Crosses_and_squares_nail_art.jpg",
        "style_hint": "geometric",
        "color_group": "dark",
        "pattern_type": "plaid",
        "notes": "graphic crosses and square layout",
    },
    {
        "title": "Complex_nail_art.jpg",
        "style_hint": "complex_art",
        "color_group": "warm",
        "pattern_type": "abstract",
        "notes": "high-complexity multi-element nail art",
    },
    {
        "title": "Biab_nagels.jpg",
        "style_hint": "biab_natural",
        "color_group": "light",
        "pattern_type": "solid",
        "notes": "builder gel / BIAB natural manicure",
    },
    {
        "title": "Natural_French_manicure.jpg",
        "style_hint": "natural_french",
        "color_group": "light",
        "pattern_type": "french",
        "notes": "natural french manicure",
    },
    {
        "title": "Blue_Nails_(6270570945).jpg",
        "style_hint": "solid_blue",
        "color_group": "cool",
        "pattern_type": "solid",
        "notes": "blue manicure reference",
    },
    {
        "title": "Animal_Print_(6463258185).jpg",
        "style_hint": "animal_print",
        "color_group": "warm",
        "pattern_type": "leopard",
        "notes": "animal print manicure",
    },
    {
        "title": "A_woman's_hands.JPG",
        "style_hint": "red_classic",
        "color_group": "warm",
        "pattern_type": "solid",
        "notes": "classic red nails on hands",
    },
]


KNOWLEDGE_TOPICS = [
    {
        "topic_id": "nail_anatomy_and_prep",
        "title": "指甲结构与前处理",
        "summary": "指甲护理和上色前应重视甲板、甲床、甲小皮的结构差异，避免过度泡水和过度修剪角质层，以提升附着力并降低感染风险。",
        "points": [
            "指甲由甲板、甲床和甲母质等部分构成，角质层不应被整圈深度剪除，否则会增加感染风险。",
            "做美甲前应先去除旧甲油、软化角质层、推后角质层、轻微抛磨，再用酒精或卸甲产品去油。",
            "泡水会让甲板暂时吸水膨胀，若在含水状态下上色，后续更容易崩边。",
            "抛磨建议使用细目数缓冲条，过低目数会增加甲板损伤风险。",
        ],
        "tags": ["anatomy", "prep", "adhesion", "cuticle"],
        "sources": [
            {
                "title": "The perfect at home DIY manicure!",
                "url": "https://www.essie.com/inspiration/tips-and-trends/how-to-prep-nail-for-manicure",
            }
        ],
    },
    {
        "topic_id": "nail_shapes",
        "title": "常见甲型与适配规则",
        "summary": "甲型选择要结合自然甲床宽度、长度和风格诉求，不同甲型在稳定性、显手长和维护成本上差异明显。",
        "points": [
            "方形甲稳定性较高，适合短甲床或窄甲面，也适用于短甲和长甲。",
            "Squoval 兼具方形与椭圆的优点，普适性强，适合大多数日常款式库冷启动。",
            "圆形甲最自然、低维护，适合通勤和基础纯色款。",
            "椭圆甲和杏仁甲更显手指修长，但对长度和边缘强度要求更高。",
            "芭蕾甲适合中长到长甲，适合高级感、韩系、婚礼和装饰型风格。",
        ],
        "tags": ["shape", "square", "round", "oval", "almond", "ballerina"],
        "sources": [
            {"title": "how to choose the right nail shape for you", "url": "https://www.essie.com/inspiration/nail-shapes"},
            {"title": "How to Shape Nails", "url": "https://www.opi.com/professionals/how-to-shape-nails"},
        ],
    },
    {
        "topic_id": "product_layers_and_finish",
        "title": "底胶、色胶、封层与质感",
        "summary": "标准流程通常由底层附着、颜色层表达和封层保护构成，顶部质感决定成品风格与维护周期。",
        "points": [
            "底胶的主要作用是增强附着力和防染色，纯色、法式、猫眼、渐变都建议建立稳定底层。",
            "颜色层通常需要 2 层表达主色，适合在 metadata 中记录主色、辅色、透明度与饱和度。",
            "封层可分高光、哑光等质感，适合作为检索字段 finish。",
            "光泽、磨砂、果冻、镜面、猫眼、亮片等质感应独立于图案类型记录，避免都挤进 category。",
        ],
        "tags": ["base_coat", "color_layer", "top_coat", "finish", "texture"],
        "sources": [
            {
                "title": "The perfect at home DIY manicure!",
                "url": "https://www.essie.com/inspiration/tips-and-trends/how-to-prep-nail-for-manicure",
            }
        ],
    },
    {
        "topic_id": "salon_safety_chemicals",
        "title": "美甲化学品与通风安全",
        "summary": "美甲场景涉及多种挥发性和刺激性化学品，通风、本地排风、容器密封和 SDS 管理是门店与培训知识库的重要组成。",
        "points": [
            "常见风险化学品包括 acetone、ethyl acetate、formaldehyde、toluene、EMA、MMA 等。",
            "OSHA 将 toluene、formaldehyde、dibutyl phthalate 归为行业常提到的 toxic trio。",
            "通风是降低暴露的首选措施，本地排风、下吸式工作台和持续 HVAC 运行都能降低暴露。",
            "SDS 应随产品提供并便于技师获取，店内应保留危害信息、储存与应急处理说明。",
            "手术口罩不能替代针对化学蒸汽的呼吸防护。",
        ],
        "tags": ["safety", "chemicals", "ventilation", "sds", "osha"],
        "sources": [
            {"title": "Health Hazards in Nail Salons - Chemical Hazards", "url": "https://www.osha.gov/nail-salons/chemical-hazards"},
            {"title": "Nail Technicians: Workplace Safety and Health", "url": "https://www.cdc.gov/niosh/nail-technicians/about/index.html"},
        ],
    },
    {
        "topic_id": "biohazard_disinfection",
        "title": "感染控制与工具消毒",
        "summary": "美甲知识库不应只有款式，还应覆盖感染控制。对有创处理、感染指甲、出血情况的判断会直接影响门店 SOP。",
        "points": [
            "若客户存在开放性伤口、起泡、明显感染或渗血，通常不应继续常规美甲服务。",
            "工具应在每位客户后清洗并按说明浸泡 EPA 注册消毒剂，之后冲洗、擦干、洁净存储。",
            "UV 盒适合存放已完成清洁消毒的金属工具，但本身不等于完整消毒流程。",
            "员工若可能接触血液或其他潜在感染物，应遵循 bloodborne pathogens 相关要求。",
        ],
        "tags": ["disinfection", "biohazard", "hygiene", "epa", "bloodborne"],
        "sources": [
            {"title": "Health Hazards in Nail Salons - Biological Hazards", "url": "https://www.osha.gov/nail-salons/biological-hazards"},
        ],
    },
    {
        "topic_id": "dataset_schema_recommendation",
        "title": "适合 RAG / 检索的美甲标签体系建议",
        "summary": "为了让向量检索与过滤稳定工作，款式图应至少按颜色、图案、质感、甲型、长度、场景、风格做多维标签。",
        "points": [
            "颜色字段建议拆成 base_color、accent_color、color_group、saturation、brightness。",
            "图案字段建议拆成 pattern_type、pattern_density、pattern_layout、accent_finger。",
            "质感字段建议单独记录 finish 或 texture，如 glossy、matte、jelly、cat_eye、chrome、glitter。",
            "形态字段建议记录 nail_shape、length、natural_or_extension。",
            "风格字段建议记录 style_genre、occasion、season、complexity，便于个性化推荐与 prompt 增强。",
        ],
        "tags": ["schema", "metadata", "retrieval", "rag"],
        "sources": [
            {"title": "Internal synthesis from fetched manicure guidance", "url": "https://www.essie.com/inspiration/nail-shapes"},
        ],
    },
]


def _http_get_json(url: str) -> dict:
    context = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "NailFlowSeedFetcher/1.0"})
    with urllib.request.urlopen(req, context=context, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_file(url: str, dest: Path, retries: int = 4) -> None:
    context = ssl.create_default_context()
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "NailFlowSeedFetcher/1.0"})
            with urllib.request.urlopen(req, context=context, timeout=60) as resp:
                dest.write_bytes(resp.read())
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last_error))


def write_knowledge_files() -> None:
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "2026-06-02",
        "language": "zh-CN",
        "topics": KNOWLEDGE_TOPICS,
    }
    (KNOWLEDGE_DIR / "nail_knowledge_seed.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 美甲专业知识种子库",
        "",
        "该文件用于补充 NailFlow 的美甲 RAG 知识侧数据，内容整理自公开网页，便于后续转成标签体系、门店 SOP 和 prompt 增强。",
        "",
    ]
    for topic in KNOWLEDGE_TOPICS:
        lines.append(f"## {topic['title']}")
        lines.append("")
        lines.append(topic["summary"])
        lines.append("")
        for point in topic["points"]:
            lines.append(f"- {point}")
        lines.append("")
        lines.append("来源：")
        for src in topic["sources"]:
            lines.append(f"- {src['title']}: {src['url']}")
        lines.append("")

    (KNOWLEDGE_DIR / "nail_knowledge_seed.md").write_text("\n".join(lines), encoding="utf-8")


def fetch_commons_image_metadata(file_name: str) -> dict:
    title = urllib.parse.quote(f"File:{file_name}", safe=":")
    api_url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2"
        f"&prop=imageinfo&iiprop=url|extmetadata&titles={title}"
    )
    payload = _http_get_json(api_url)
    page = payload["query"]["pages"][0]
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    return {
        "title": file_name,
        "canonical_title": page.get("title", f"File:{file_name}"),
        "description_url": info.get("descriptionurl", ""),
        "download_url": info.get("url", ""),
        "artist": (meta.get("Artist") or {}).get("value", ""),
        "license_short_name": (meta.get("LicenseShortName") or {}).get("value", ""),
        "license_url": (meta.get("LicenseUrl") or {}).get("value", ""),
        "image_description": (meta.get("ImageDescription") or {}).get("value", ""),
        "date_time": (meta.get("DateTime") or {}).get("value", ""),
        "credit": (meta.get("Credit") or {}).get("value", ""),
    }


def fetch_and_download_commons_images() -> None:
    COMMONS_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for item in COMMONS_FILES:
        record = {**item}
        api_meta = fetch_commons_image_metadata(item["title"])
        record.update(api_meta)
        download_url = record.get("download_url")
        file_name = Path(urllib.parse.unquote(item["title"])).name
        dest = COMMONS_DIR / file_name

        if dest.exists():
            record["downloaded"] = True
            record["local_path"] = str(dest)
            record["file_size"] = dest.stat().st_size
            records.append(record)
            continue

        if not download_url:
            record["downloaded"] = False
            record["error"] = "missing download url"
            records.append(record)
            continue

        try:
            _download_file(download_url, dest)
            record["downloaded"] = True
            record["local_path"] = str(dest)
            record["file_size"] = dest.stat().st_size
        except Exception as exc:  # noqa: BLE001
            record["downloaded"] = False
            record["error"] = str(exc)
        records.append(record)
        time.sleep(0.2)

    manifest = {
        "version": "2026-06-02",
        "source": "Wikimedia Commons",
        "license_notice": "请按各图片记录中的 license_short_name / license_url 做署名与兼容性检查后再商用。",
        "images": records,
    }
    (COMMONS_DIR / "commons_nail_images.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    write_knowledge_files()
    fetch_and_download_commons_images()
    print("seed nail assets fetched")


if __name__ == "__main__":
    main()
