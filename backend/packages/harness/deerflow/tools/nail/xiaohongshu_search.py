# tools/nail/xiaohongshu_search.py
"""小红书搜索工具 — 供 Agent 在运营分析时获取外部市场数据。"""
from __future__ import annotations

import json
import logging
import os

from langchain.tools import tool

logger = logging.getLogger(__name__)

_COOKIE_HEALTH_CHECKED = False
_COOKIE_HEALTHY = False


def _check_cookie() -> str | None:
    """检查 Cookie 状态，返回诊断信息。"""
    global _COOKIE_HEALTH_CHECKED, _COOKIE_HEALTHY

    if _COOKIE_HEALTH_CHECKED:
        return None if _COOKIE_HEALTHY else "Cookie 未配置或已失效"

    _COOKIE_HEALTH_CHECKED = True
    cookie = os.getenv("XIAOHONGSHU_COOKIE") or os.getenv("XHS_COOKIE") or ""

    if not cookie:
        return "未配置 XIAOHONGSHU_COOKIE 环境变量"

    # 简单校验：有效 Cookie 至少 100 字符
    if len(cookie) < 100:
        return "Cookie 过短，可能不完整"

    _COOKIE_HEALTHY = True
    return None


@tool
def xiaohongshu_search_tool(
    keyword: str = "",
    topic: str = "美甲",
    top_n: int = 10,
) -> str:
    """搜索小红书上美甲相关帖子，获取热门趋势和用户偏好数据。

    用于运营分析时补充外部市场数据，了解小红书美甲趋势。
    与内部 ops_signals 数据交叉验证，发现新品类机会。

    Args:
        keyword: 搜索关键词，如"猫眼美甲"、"夏日美甲"、"穿戴甲"
        topic: 话题标签，默认"美甲"
        top_n: 返回条数，默认 10，最大 20

    Returns:
        JSON 字符串:
        {"posts": [{"title":"..","description":"..","likes":N,"comments":N,
          "saves":N,"tags":["美甲"],"url":"https://...","published_at":"..",
          "source":"api|fallback"}],
         "count": N, "cookie_ok": true, "error": null}
    """
    try:
        import asyncio
        import concurrent.futures

        from .xhs_client import search_posts

        limit = min(top_n, 20)
        cookie_diag = _check_cookie()

        # 在独立线程中运行异步搜索，避免事件循环冲突
        def _run_async():
            return asyncio.run(search_posts(keyword, limit))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            posts = pool.submit(_run_async).result(timeout=60)

        # 判断数据来源
        data_source = posts[0].get("source", "fallback") if posts else "fallback"

        return json.dumps({
            "posts": posts,
            "count": len(posts),
            "source": data_source,
            "cookie_ok": cookie_diag is None,
            "cookie_hint": cookie_diag,
            "error": None,
        }, ensure_ascii=False)

    except ImportError as e:
        logger.warning("XHS search dependency missing: %s", e)
        return json.dumps({
            "posts": [],
            "count": 0,
            "source": "fallback",
            "cookie_ok": False,
            "cookie_hint": str(e),
            "error": f"依赖缺失: {e}",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error("xiaohongshu_search_tool failed: %s", e)
        return json.dumps({
            "posts": [],
            "count": 0,
            "source": "fallback",
            "cookie_ok": False,
            "cookie_hint": str(e),
            "error": str(e),
        }, ensure_ascii=False)
