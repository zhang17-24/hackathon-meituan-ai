#!/usr/bin/env python3
"""批量抓取 Wikimedia Commons 美甲图片（分类浏览方案，API 请求少、内容精准）。

分类比全文搜索精准（Category:Nail art / Manicure 下的文件都是美甲图），
且用 categorymembers + 批量 imageinfo 合并请求，限流风险低。

用法：cd backend && uv run python scripts/bulk_fetch_style_images.py [--per-category 120]

输出：
- data/styles/commons/{title} — 下载的图片（license 兼容的）
- data/styles/commons/bulk_manifest.json — 候选记录
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "data" / "styles" / "commons"

CATEGORIES = [
    "Category:Nail art",
    "Category:Manicure",
]

_API_BASE = "https://commons.wikimedia.org/w/api.php"
_UA = {"User-Agent": "nailflowStyleCrawler/1.0 (hackathon demo)"}


def _http_get_json(params: dict) -> dict:
    context = ssl.create_default_context()
    params.setdefault("format", "json")
    params.setdefault("formatversion", "2")
    url = f"{_API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, context=context, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_file(url: str, dest: Path, retries: int = 2) -> None:
    context = ssl.create_default_context()
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_UA)
            with urllib.request.urlopen(req, context=context, timeout=40) as resp:
                dest.write_bytes(resp.read())
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(0.5)
    raise RuntimeError(str(last_error))


def _looks_license_compatible(license_short_name: str) -> bool:
    value = (license_short_name or "").lower()
    return any(token in value for token in ("cc", "public domain", "pd"))


def _list_category_files(category: str, limit: int) -> list[str]:
    """翻页列出分类下的全部文件。"""
    titles: list[str] = []
    params = {
        "action": "query",
        "generator": "categorymembers",
        "gcmtitle": category,
        "gcmtype": "file",
        "gcmlimit": 50,
    }
    for _ in range((limit // 50) + 1):
        try:
            payload = _http_get_json(params)
        except Exception:  # noqa: BLE001
            break
        pages = payload.get("query", {}).get("pages", [])
        for page in pages:
            title = page.get("title", "")
            if title.startswith("File:"):
                titles.append(title)
        if "continue" not in payload or len(titles) >= limit:
            break
        cont = payload["continue"]
        params["gcmcontinue"] = cont.get("gcmcontinue")
        params["continue"] = cont.get("continue")
        time.sleep(0.5)
    return titles[:limit]


def _fetch_batch_metadata(titles: list[str]) -> list[dict]:
    """批量获取 imageinfo（50 个/请求），带 400px thumb URL。

    Commons 官方建议爬虫使用 thumb 尺寸（有专用缓存层，原图下载易被限流）。
    """
    records: list[dict] = []
    for i in range(0, len(titles), 50):
        batch = titles[i : i + 50]
        try:
            payload = _http_get_json({
                "action": "query",
                "prop": "imageinfo",
                "iiprop": "url|size|extmetadata",
                "iiurlwidth": 480,
                "titles": "|".join(batch),
            })
        except Exception as exc:  # noqa: BLE001
            print(f"  ! 元数据获取失败: {exc}", flush=True)
            continue
        for page in payload.get("query", {}).get("pages", []):
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            records.append({
                "canonical_title": page.get("title", ""),
                "description_url": info.get("descriptionurl", ""),
                "download_url": info.get("url", ""),
                "thumb_url": info.get("thumburl", ""),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
                "license_short_name": (meta.get("LicenseShortName") or {}).get("value", ""),
                "license_url": (meta.get("LicenseUrl") or {}).get("value", ""),
                "image_description": (meta.get("ImageDescription") or {}).get("value", ""),
            })
        time.sleep(0.5)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="分类浏览抓取 Commons 美甲图片")
    parser.add_argument("--per-category", type=int, default=120, help="每分类最多取文件数")
    parser.add_argument("--min-size", type=int, default=400, help="最小边长")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"分类: {CATEGORIES}, 每分类上限: {args.per_category}")

    all_titles: list[str] = []
    for cat in CATEGORIES:
        titles = _list_category_files(cat, args.per_category)
        print(f"  {cat}: 列出 {len(titles)} 个文件", flush=True)
        all_titles.extend(titles)

    seen = set()
    all_titles = [t for t in all_titles if not (t in seen or seen.add(t))]
    print(f"去重后共 {len(all_titles)} 个文件，获取元数据...", flush=True)

    metas = _fetch_batch_metadata(all_titles)
    print(f"元数据 {len(metas)} 条，开始筛选与下载...", flush=True)

    candidates = []
    for m in metas:
        file_name = Path(urllib.parse.unquote(m["canonical_title"].replace("File:", "", 1))).name
        local_path = OUT_DIR / file_name
        # 优先用 480px thumb（官方推荐爬虫尺寸），失败时回退原图 URL
        fetch_url = m.get("thumb_url") or m.get("download_url", "")
        record = {
            "title": file_name,
            "category_source": "commons",
            "source_url": m.get("description_url", ""),
            "width": m.get("width", 0),
            "height": m.get("height", 0),
            "license_short_name": m.get("license_short_name", ""),
            "license_url": m.get("license_url", ""),
            "download_url": fetch_url,
            "image_description": m.get("image_description", ""),
            "license_compatible": _looks_license_compatible(m.get("license_short_name", "")),
            "downloaded": False,
            "local_path": str(local_path),
        }
        if not record["license_compatible"]:
            record["skipped"] = "bad_license"
        elif m.get("width", 0) < args.min_size or m.get("height", 0) < args.min_size:
            record["skipped"] = "too_small"
        else:
            candidates.append(record)

    skipped_license = sum(1 for r in candidates if r.get("skipped") == "bad_license")
    skipped_size = sum(1 for r in candidates if r.get("skipped") == "too_small")

    def download(rec: dict) -> dict:
        if rec.get("skipped"):
            return rec
        local_path = Path(rec["local_path"])
        if local_path.exists():
            rec["downloaded"] = True
            rec["file_size"] = local_path.stat().st_size
            return rec
        try:
            _download_file(rec["download_url"], local_path)
            rec["downloaded"] = True
            rec["file_size"] = local_path.stat().st_size
            print(f"  [OK] {rec['title']} ({rec['width']}x{rec['height']}, {rec['license_short_name']})", flush=True)
        except Exception as exc:  # noqa: BLE001
            rec["error"] = str(exc)
        time.sleep(0.6)
        return rec

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(download, candidates))

    downloaded = sum(1 for r in results if r.get("downloaded"))
    manifest_path = OUT_DIR / "bulk_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "2026-08-27",
                "source": "Wikimedia Commons Categories",
                "categories": CATEGORIES,
                "candidate_count": len(results),
                "downloaded_count": downloaded,
                "skipped_bad_license": skipped_license,
                "skipped_too_small": skipped_size,
                "images": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n完成: 候选 {len(results)}, 下载 {downloaded}, 许可跳过 {skipped_license}, 尺寸跳过 {skipped_size}", flush=True)
    print(f"manifest: {manifest_path}", flush=True)


if __name__ == "__main__":
    main()
