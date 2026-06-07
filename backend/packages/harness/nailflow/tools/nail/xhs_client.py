# tools/nail/xhs_client.py
"""小红书数据获取：内部 API 搜索 + HTML 页面提取 + 静态降级。

搜索策略（按优先级）:
  1. 小红书内部搜索 API（需要有效 Cookie）
  2. 搜索页 HTML 中提取 noteId（SEO 渲染内容）
  3. 静态降级 — 返回搜索页 URL 供人工查阅

提取策略（按优先级）:
  1. 直接请求帖子页面 HTML，解析 __INITIAL_STATE__
  2. 降级返回搜索页引用
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import sys
import time

import httpx

logger = logging.getLogger(__name__)

# XHS-Downloader 路径（提取备用）
_XHS_PATH = "/Users/xinyiji/Desktop/XHS-Downloader"
if _XHS_PATH not in sys.path:
    sys.path.insert(0, _XHS_PATH)

_DEFAULT_DELAY = 6.0

# ── 静态降级：热门关键词 → 搜索页 URL ──
# 当所有在线策略失败时，至少返回可点击的搜索链接
_FALLBACK_KEYWORD_URLS: dict[str, str] = {
    "美甲":     "https://www.xiaohongshu.com/search_result/?keyword=%E7%BE%8E%E7%94%B2&type=51",
    "穿戴甲":   "https://www.xiaohongshu.com/search_result/?keyword=%E7%A9%BF%E6%88%B4%E7%94%B2&type=51",
    "猫眼美甲": "https://www.xiaohongshu.com/search_result/?keyword=%E7%8C%AB%E7%9C%BC%E7%BE%8E%E7%94%B2&type=51",
    "夏日美甲": "https://www.xiaohongshu.com/search_result/?keyword=%E5%A4%8F%E6%97%A5%E7%BE%8E%E7%94%B2&type=51",
    "秋冬美甲": "https://www.xiaohongshu.com/search_result/?keyword=%E7%A7%8B%E5%86%AC%E7%BE%8E%E7%94%B2&type=51",
    "法式美甲": "https://www.xiaohongshu.com/search_result/?keyword=%E6%B3%95%E5%BC%8F%E7%BE%8E%E7%94%B2&type=51",
    "渐变美甲": "https://www.xiaohongshu.com/search_result/?keyword=%E6%B8%90%E5%8F%98%E7%BE%8E%E7%94%B2&type=51",
    "裸色美甲": "https://www.xiaohongshu.com/search_result/?keyword=%E8%A3%B8%E8%89%B2%E7%BE%8E%E7%94%B2&type=51",
    "红色美甲": "https://www.xiaohongshu.com/search_result/?keyword=%E7%BA%A2%E8%89%B2%E7%BE%8E%E7%94%B2&type=51",
    "钻美甲":   "https://www.xiaohongshu.com/search_result/?keyword=%E9%92%BB%E7%BE%8E%E7%94%B2&type=51",
    "蝴蝶结美甲": "https://www.xiaohongshu.com/search_result/?keyword=%E8%9D%B4%E8%9D%B6%E7%BB%93%E7%BE%8E%E7%94%B2&type=51",
}

_BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def _get_cookie() -> str:
    return os.getenv("XIAOHONGSHU_COOKIE") or os.getenv("XHS_COOKIE") or ""


def _parse_int(val: str) -> int:
    val = str(val).strip()
    if not val:
        return 0
    try:
        if "万" in val:
            return int(float(val.replace("万", "")) * 10000)
        return int(val)
    except (ValueError, TypeError):
        return 0


# ── 搜索 ──

async def _search_via_api(keyword: str, count: int) -> list[str]:
    """小红书内部搜索 API。

    POST edith.xiaohongshu.com/api/sns/web/v1/search/notes
    需要有效 Cookie，否则返回账号异常错误。
    """
    cookie = _get_cookie()
    if not cookie:
        logger.info("XHS API search skipped: no cookie set")
        return []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes",
                headers={
                    **_BASE_HEADERS,
                    "Content-Type": "application/json; charset=utf-8",
                    "Origin": "https://www.xiaohongshu.com",
                    "Referer": "https://www.xiaohongshu.com/",
                    "Cookie": cookie,
                },
                json={
                    "keyword": keyword,
                    "page": 1,
                    "page_size": min(count, 20),
                    "sort": "general",
                    "note_type": 0,
                },
            )
            if resp.status_code != 200:
                logger.warning("XHS API returned %d", resp.status_code)
                return []

            data = resp.json()
            if not data.get("success"):
                msg = data.get("msg", "unknown")
                logger.warning("XHS API search failed: %s", msg)
                return []

            urls: list[str] = []
            for item in data.get("data", {}).get("items", []):
                note_card = item.get("note_card") or item
                note_id = note_card.get("note_id", "")
                if note_id:
                    urls.append(f"https://www.xiaohongshu.com/explore/{note_id}")

            logger.info("XHS API: %d URLs for keyword=%s", len(urls), keyword)
            return urls[:count]

    except Exception:
        logger.warning("XHS API exception for keyword=%s", keyword)
        return []


async def _search_via_html(keyword: str, count: int) -> list[str]:
    """从搜索页 HTML 中提取 noteId。

    小红书搜索页的 __INITIAL_STATE__ 中可能包含部分 SSR 渲染的帖子数据。
    """
    cookie = _get_cookie()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.xiaohongshu.com/search_result/",
                params={"keyword": keyword, "type": 51},
                headers={**_BASE_HEADERS, "Referer": "https://www.xiaohongshu.com/"},
            )
            if resp.status_code != 200:
                return []

            html = resp.text

            # 从 __INITIAL_STATE__ 中提取 noteDetailMap 中的帖子
            match = re.search(
                r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*</script>',
                html,
                re.DOTALL,
            )
            if not match:
                return []

            raw = match.group(1)
            raw = re.sub(r':\s*undefined', ': null', raw)
            state = json.loads(raw)

            note_map = state.get("note", {}).get("noteDetailMap", {})
            # noteId 是 24 位十六进制字符串，过滤掉 "undefined" 等无效值
            _VALID_NOTE_ID = re.compile(r'^[a-f0-9]{24}$')
            urls = [
                f"https://www.xiaohongshu.com/explore/{nid}"
                for nid in note_map.keys()
                if _VALID_NOTE_ID.match(nid)
            ]
            if urls:
                logger.info("HTML extract: %d valid URLs from search page", len(urls))
            return urls[:count]

    except Exception:
        logger.debug("HTML search exception for keyword=%s", keyword)
        return []


async def _search_urls(keyword: str, count: int) -> list[str]:
    """多策略搜索小红书帖子 URL。

    策略: 内部 API → HTML 提取 → 静态降级
    """
    full_keyword = keyword if keyword else "美甲"

    # 策略 1: 内部搜索 API
    urls = await _search_via_api(full_keyword, count)
    if urls:
        return urls

    # 策略 2: 搜索页 HTML 提取
    urls = await _search_via_html(full_keyword, count)
    if urls:
        return urls

    # 策略 3: 静态降级
    best_match = None
    for k, v in _FALLBACK_KEYWORD_URLS.items():
        if k in keyword or keyword in k:
            best_match = v
            break
    fallback = best_match or _FALLBACK_KEYWORD_URLS.get("美甲", "")
    logger.warning("All search strategies exhausted for keyword=%s, using fallback", keyword)
    return [fallback] if fallback else []


# ── 帖子提取 ──

async def _extract_post_html(url: str) -> dict | None:
    """直接请求帖子页面，解析 __INITIAL_STATE__ 提取数据。"""
    cookie = _get_cookie()

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={**_BASE_HEADERS, "Referer": "https://www.xiaohongshu.com/", "Cookie": cookie},
            )

            # 检查是否被重定向到 404 或需要验证
            final_url = str(resp.url)
            if "/404" in final_url or resp.status_code != 200:
                logger.debug("Post unavailable: %s → %s", url, final_url)
                return None

            html = resp.text
            if len(html) < 5000:
                logger.debug("Post page too short (likely blocked): %s", url)
                return None

            # 提取 __INITIAL_STATE__
            match = re.search(
                r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*</script>',
                html,
                re.DOTALL,
            )
            if not match:
                return None

            raw = re.sub(r':\s*undefined', ': null', match.group(1))
            state = json.loads(raw)

            note_map = state.get("note", {}).get("noteDetailMap", {})
            if not note_map:
                return None

            detail = next(iter(note_map.values()), {})
            note_data = detail.get("note", {})
            if not note_data:
                return None

            interact = note_data.get("interactInfo", {})
            user = note_data.get("user", {})
            tags = [t.get("name", "") for t in note_data.get("tagList", [])]

            published_at = ""
            ts = note_data.get("time")
            if ts:
                published_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts / 1000))

            return {
                "title": note_data.get("title", ""),
                "description": note_data.get("desc", ""),
                "likes": _parse_int(interact.get("likedCount", "0")),
                "comments": _parse_int(interact.get("commentCount", "0")),
                "saves": _parse_int(interact.get("collectedCount", "0")),
                "tags": tags,
                "url": url,
                "published_at": published_at,
                "author": user.get("nickname", user.get("nickName", "")),
            }

    except Exception as e:
        logger.debug("Post extraction failed for %s: %s", url, e)
        return None


async def _extract_posts(urls: list[str]) -> list[dict]:
    """批量提取帖子详情。跳过搜索页 URL。"""
    if not urls:
        return []

    posts: list[dict] = []

    for i, url in enumerate(urls):
        if "/search_result" in url:
            continue

        try:
            data = await _extract_post_html(url)
            if data:
                posts.append(data)
        except Exception as e:
            logger.debug("Extract failed for %s: %s", url, e)

        if i < len(urls) - 1:
            delay = max(1.0, random.lognormvariate(1.5, 0.5))
            await asyncio.sleep(min(delay, _DEFAULT_DELAY))

    return posts


# ── 公开接口 ──

async def search_posts(keyword: str, top_n: int = 10) -> list[dict]:
    """搜索小红书美甲帖子。

    Args:
        keyword: 搜索关键词，如"猫眼美甲"、"夏日美甲"、"穿戴甲"
        top_n: 最大返回条数，默认 10，最大 20

    Returns:
        [{"title","description","likes","comments","saves","tags","url","published_at","source"}, ...]
        source 字段标识数据来源: "api" | "html" | "fallback"
    """
    limit = min(top_n, 20)

    # 阶段 1: 搜索 URL
    urls = await _search_urls(keyword, limit)

    # 阶段 2: 提取详情
    if urls:
        # 检查是否降级到搜索页
        if all("/search_result" in u for u in urls):
            return [{
                "title": f"小红书搜索: {keyword}",
                "description": (
                    "搜索数据暂时不可用（Cookie 可能已过期或被风控）。"
                    "请点击链接在浏览器中查看小红书搜索结果。"
                ),
                "likes": 0,
                "comments": 0,
                "saves": 0,
                "tags": [keyword, "美甲"],
                "url": urls[0],
                "published_at": "",
                "author": "",
                "source": "fallback",
            }]

        posts = await _extract_posts(urls[:limit])
        for p in posts:
            p["source"] = "api"
        if posts:
            return posts

    return [{
        "title": f"小红书搜索: {keyword}",
        "description": "暂无搜索结果，请检查网络或 Cookie 配置",
        "likes": 0,
        "comments": 0,
        "saves": 0,
        "tags": [keyword, "美甲"],
        "url": _FALLBACK_KEYWORD_URLS.get("美甲", ""),
        "published_at": "",
        "author": "",
        "source": "fallback",
    }]
