#!/usr/bin/env python3
"""Search openly licensed nail images and export a manifest.

Outputs:
- data/seed_images/commons/commons_search_manifest.json
- optional downloaded image files under data/seed_images/commons/
"""

from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
COMMONS_DIR = BASE_DIR / "data" / "seed_images" / "commons"


@dataclass(frozen=True)
class SearchKeyword:
    query: str
    style_hint: str
    color_group: str
    pattern_type: str


KEYWORDS: list[SearchKeyword] = [
    SearchKeyword("french manicure nails", "french", "light", "french"),
    SearchKeyword("gradient nail art", "gradient", "", "gradient"),
    SearchKeyword("cat eye nails", "cat_eye", "cool", "cat_eye"),
    SearchKeyword("jelly nails", "jelly", "light", "jelly"),
    SearchKeyword("leopard nail art", "animal_print", "warm", "leopard"),
    SearchKeyword("floral nail art", "floral", "cool", "floral"),
    SearchKeyword("short nude nails", "short_nude", "light", "solid"),
    SearchKeyword("red manicure nails", "classic_red", "warm", "solid"),
]


def _http_get_json(url: str) -> dict:
    context = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "nailflowImageCrawler/1.0"})
    with urllib.request.urlopen(req, context=context, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_file(url: str, dest: Path, retries: int = 4) -> None:
    context = ssl.create_default_context()
    last_error = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nailflowImageCrawler/1.0"})
            with urllib.request.urlopen(req, context=context, timeout=60) as resp:
                dest.write_bytes(resp.read())
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last_error))


def _search_commons_files(query: str, limit: int) -> list[str]:
    encoded_query = urllib.parse.quote(query)
    api_url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2"
        f"&generator=search&gsrsearch={encoded_query}"
        f"&gsrnamespace=6&gsrlimit={max(1, limit)}"
    )
    payload = _http_get_json(api_url)
    pages = payload.get("query", {}).get("pages", [])
    return [page.get("title", "") for page in pages if page.get("title", "").startswith("File:")]


def _fetch_commons_image_metadata(file_title: str) -> dict:
    title = urllib.parse.quote(file_title, safe=":")
    api_url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2"
        f"&prop=imageinfo&iiprop=url|extmetadata&titles={title}"
    )
    payload = _http_get_json(api_url)
    page = payload["query"]["pages"][0]
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    return {
        "canonical_title": page.get("title", file_title),
        "description_url": info.get("descriptionurl", ""),
        "download_url": info.get("url", ""),
        "artist": (meta.get("Artist") or {}).get("value", ""),
        "license_short_name": (meta.get("LicenseShortName") or {}).get("value", ""),
        "license_url": (meta.get("LicenseUrl") or {}).get("value", ""),
        "image_description": (meta.get("ImageDescription") or {}).get("value", ""),
        "date_time": (meta.get("DateTime") or {}).get("value", ""),
        "credit": (meta.get("Credit") or {}).get("value", ""),
    }


def _looks_license_compatible(license_short_name: str) -> bool:
    value = (license_short_name or "").lower()
    return any(token in value for token in ("cc", "public domain", "pd"))


def crawl_commons_manifest(
    limit_per_keyword: int = 4,
    max_keywords: int = 0,
    download_limit: int = 0,
) -> dict:
    COMMONS_DIR.mkdir(parents=True, exist_ok=True)
    selected_keywords = KEYWORDS[:max_keywords] if max_keywords > 0 else KEYWORDS

    manifest_records = []
    seen_titles: set[str] = set()
    downloads_done = 0

    for keyword in selected_keywords:
        titles = _search_commons_files(keyword.query, limit=limit_per_keyword)
        for title in titles:
            if title in seen_titles:
                continue
            seen_titles.add(title)

            meta = _fetch_commons_image_metadata(title)
            file_name = Path(urllib.parse.unquote(title.replace("File:", "", 1))).name
            local_path = COMMONS_DIR / file_name

            record = {
                "title": file_name,
                "search_query": keyword.query,
                "source": "Wikimedia Commons",
                "source_url": meta.get("description_url", ""),
                "style_hint": keyword.style_hint,
                "color_group": keyword.color_group,
                "pattern_type": keyword.pattern_type,
                "downloaded": False,
                "local_path": str(local_path),
                "license_short_name": meta.get("license_short_name", ""),
                "license_url": meta.get("license_url", ""),
                "artist": meta.get("artist", ""),
                "download_url": meta.get("download_url", ""),
                "image_description": meta.get("image_description", ""),
                "canonical_title": meta.get("canonical_title", title),
                "date_time": meta.get("date_time", ""),
                "credit": meta.get("credit", ""),
                "license_compatible": _looks_license_compatible(meta.get("license_short_name", "")),
            }

            if download_limit > 0 and downloads_done < download_limit and record["download_url"] and record["license_compatible"]:
                try:
                    if not local_path.exists():
                        _download_file(record["download_url"], local_path)
                    record["downloaded"] = True
                    if local_path.exists():
                        record["file_size"] = local_path.stat().st_size
                    downloads_done += 1
                except Exception as exc:  # noqa: BLE001
                    record["error"] = str(exc)

            manifest_records.append(record)
            time.sleep(0.2)

    manifest = {
        "version": "2026-06-02",
        "source": "Wikimedia Commons Search",
        "keyword_count": len(selected_keywords),
        "image_count": len(manifest_records),
        "license_notice": "请结合各条记录中的 license_short_name 与 license_url 做兼容性检查后再用于商用。",
        "images": manifest_records,
    }
    manifest_path = COMMONS_DIR / "commons_search_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "manifest_path": str(manifest_path),
        "image_count": len(manifest_records),
        "downloads_done": downloads_done,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取 Wikimedia Commons 美甲图片 manifest")
    parser.add_argument("--limit-per-keyword", type=int, default=4, help="每个关键词抓取的候选图片数")
    parser.add_argument("--max-keywords", type=int, default=0, help="仅使用前 N 个关键词，0 表示全部")
    parser.add_argument("--download-limit", type=int, default=0, help="可选，最多下载 N 张开放授权图片")
    args = parser.parse_args()

    result = crawl_commons_manifest(
        limit_per_keyword=args.limit_per_keyword,
        max_keywords=args.max_keywords,
        download_limit=args.download_limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
