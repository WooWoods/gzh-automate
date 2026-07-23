#!/usr/bin/env python3
"""
Fetch trending topics from multiple Chinese platforms.

Sources (all attempted in parallel, results merged and deduplicated):
  1. Weibo hot search (weibo.com/ajax/side/hotSearch)
  2. Toutiao hot board (toutiao.com/hot-event/hot-board)
  3. Baidu hot search (top.baidu.com/api/board)

Usage:
    wewrite hotspots --limit 20
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta

import time

import requests

TIMEOUT = (10, 15)  # (connect_timeout, read_timeout)
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # seconds between retries
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


def _request_with_retry(url: str, headers: dict = None, source: str = "unknown") -> requests.Response:
    """GET request with exponential backoff retry on network errors."""
    hdrs = {**HEADERS, **(headers or {})}
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=hdrs, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"[warn] {source} attempt {attempt + 1} failed: {e}, retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
    raise last_exc


def fetch_weibo() -> list[dict]:
    """Fetch Weibo hot search."""
    try:
        resp = _request_with_retry(
            "https://weibo.com/ajax/side/hotSearch",
            headers={"Referer": "https://weibo.com/"},
            source="weibo",
        )
        data = resp.json()
        items = []
        for entry in data.get("data", {}).get("realtime", []):
            note = entry.get("note", "")
            if not note:
                continue
            items.append({
                "title": note,
                "source": "微博",
                "hot": entry.get("num", 0),
                "url": f"https://s.weibo.com/weibo?q=%23{note}%23",
                "description": entry.get("label_name", ""),
            })
        return items
    except Exception as e:
        print(f"[warn] weibo failed: {e}", file=sys.stderr)
        return []


def fetch_toutiao() -> list[dict]:
    """Fetch Toutiao hot board."""
    try:
        resp = _request_with_retry(
            "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
            source="toutiao",
        )
        data = resp.json()
        items = []
        for entry in data.get("data", []):
            title = entry.get("Title", "")
            if not title:
                continue
            items.append({
                "title": title,
                "source": "今日头条",
                "hot": int(entry.get("HotValue", 0) or 0),
                "url": entry.get("Url", ""),
                "description": "",
            })
        return items
    except Exception as e:
        print(f"[warn] toutiao failed: {e}", file=sys.stderr)
        return []


def fetch_baidu() -> list[dict]:
    """Fetch Baidu hot search."""
    try:
        resp = _request_with_retry(
            "https://top.baidu.com/api/board?platform=wise&tab=realtime",
            source="baidu",
        )
        data = resp.json()
        items = []
        # Baidu nests items inside cards[0].content[0].content
        for card in data.get("data", {}).get("cards", []):
            top_content = card.get("content", [])
            if not top_content:
                continue
            entries = top_content[0].get("content", []) if isinstance(top_content[0], dict) else top_content
            for entry in entries:
                word = entry.get("word", "")
                if not word:
                    continue
                items.append({
                    "title": word,
                    "source": "百度",
                    "hot": int(entry.get("hotScore", 0) or 0),
                    "url": entry.get("url", ""),
                    "description": "",
                })
        return items
    except Exception as e:
        print(f"[warn] baidu failed: {e}", file=sys.stderr)
        return []


# --- Unified API (60s.viki.moe) ---

# Platform key → display name for the unified API
_UNIFIED_PLATFORM_LABELS: dict[str, str] = {
    "zhihu": "知乎",
    "bilibili": "B站",
    "douyin": "抖音",
    "douban": "豆瓣",
    "thepaper": "澎湃新闻",
    "36kr": "36氪",
    "ithome": "IT之家",
}


def _parse_heat_value(raw_heat) -> int:
    """Parse a heat value that may be a string like '123.4万' or '1.2亿'."""
    if isinstance(raw_heat, (int, float)):
        return int(raw_heat)
    if isinstance(raw_heat, str):
        raw_heat = raw_heat.strip()
        multipliers = {"亿": 100000000, "万": 10000}
        for suffix, mult in multipliers.items():
            if suffix in raw_heat:
                try:
                    return int(float(raw_heat.replace(suffix, "")) * mult)
                except ValueError:
                    continue
        try:
            return int(float(raw_heat))
        except ValueError:
            return 0
    return 0


def fetch_unified(platform: str) -> list[dict]:
    """Fetch hot topics from a platform via the unified API (60s.viki.moe).

    This is a fast, stable aggregator that returns structured JSON for
    10 Chinese platforms. Use as Tier 1 for new platforms; native API
    can serve as Tier 2 fallback.

    Args:
        platform: Platform key recognized by the unified API
                   (e.g. 'zhihu', 'bilibili', 'douyin').

    Returns:
        List of standardized item dicts, or [] on any failure.
    """
    try:
        resp = _request_with_retry(
            f"https://60s.viki.moe/v2/{platform}",
            source=f"unified:{platform}",
        )
        data = resp.json()
        if not isinstance(data, dict) or "data" not in data:
            return []

        label = _UNIFIED_PLATFORM_LABELS.get(platform, platform)
        items = []
        for idx, entry in enumerate(data["data"]):
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            items.append({
                "title": title,
                "source": label,
                "hot": _parse_heat_value(entry.get("hot", 0)),
                "url": entry.get("url", "") or "",
                "description": "",
            })
        return items
    except Exception as e:
        print(f"[warn] unified:{platform} failed: {e}", file=sys.stderr)
        return []


def fetch_zhihu() -> list[dict]:
    """Fetch Zhihu hot list via native API.

    Uses zhihu.com/api/v3/feed/topstory/hot-list-web which returns
    structured JSON with target.title, target.excerpt, and detail_text.
    """
    try:
        resp = _request_with_retry(
            "https://www.zhihu.com/api/v3/feed/topstory/hot-list-web",
            source="zhihu",
        )
        data = resp.json()
        items = []
        for entry in data.get("data", []):
            target = entry.get("target", {})
            title = (target.get("title") or "").strip()
            if not title:
                continue
            excerpt = (target.get("excerpt") or "")[:100]
            # detail_text is a Chinese string like "1000 万热度" — parse it
            heat = _parse_heat_value(entry.get("detail_text", ""))
            items.append({
                "title": title,
                "source": "知乎",
                "hot": heat,
                "url": f"https://www.zhihu.com/question/{target.get('id', '')}",
                "description": excerpt,
            })
        return items
    except Exception as e:
        print(f"[warn] zhihu failed: {e}", file=sys.stderr)
        return []


def fetch_bilibili() -> list[dict]:
    """Fetch Bilibili popular videos via native API.

    Uses api.bilibili.com/x/web-interface/popular which returns
    the current top videos with view/like/reply stats.
    """
    try:
        resp = _request_with_retry(
            "https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1",
            source="bilibili",
        )
        data = resp.json()
        items = []
        for entry in data.get("data", {}).get("list", []):
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            stat = entry.get("stat", {})
            items.append({
                "title": title,
                "source": "B站",
                "hot": int(stat.get("view", 0) or 0),
                "url": f"https://www.bilibili.com/video/{entry.get('bvid', '')}",
                "description": entry.get("tname", ""),
            })
        return items
    except Exception as e:
        print(f"[warn] bilibili failed: {e}", file=sys.stderr)
        return []


def deduplicate(items: list[dict]) -> list[dict]:
    """Remove duplicates by exact title match."""
    seen = set()
    result = []
    for item in items:
        title = item["title"].strip()
        if title and title not in seen:
            seen.add(title)
            result.append(item)
    return result


def main():
    parser = argparse.ArgumentParser(description="Fetch trending topics")
    parser.add_argument("--limit", type=int, default=20, help="Max items to return")
    args = parser.parse_args()

    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_items = []
    sources_ok = []
    sources_fail = []

    fetchers = {"weibo": fetch_weibo, "toutiao": fetch_toutiao, "baidu": fetch_baidu}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fn): name for name, fn in fetchers.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                items = future.result()
            except Exception as e:
                print(f"[warn] {name} failed: {e}", file=sys.stderr)
                items = []
            if items:
                sources_ok.append(name)
                all_items.extend(items)
            else:
                sources_fail.append(name)

    all_items = deduplicate(all_items)

    # Normalize hot values across platforms (different scales: toutiao ~10M, weibo ~1M, baidu ~100K)
    # Strategy: within each source, rank-based score 0-100, so cross-platform sorting is fair
    by_source: dict[str, list[dict]] = {}
    for item in all_items:
        by_source.setdefault(item["source"], []).append(item)

    for source, items in by_source.items():
        items.sort(key=lambda x: int(x.get("hot", 0) or 0), reverse=True)
        n = len(items)
        for rank, item in enumerate(items):
            # Top item = 100, linear decay to ~1 for last item
            item["hot_normalized"] = round(100 * (n - rank) / n, 1) if n > 0 else 0

    all_items.sort(key=lambda x: x.get("hot_normalized", 0), reverse=True)
    all_items = all_items[:args.limit]

    tz = timezone(timedelta(hours=8))
    output = {
        "timestamp": datetime.now(tz).isoformat(),
        "sources": sources_ok,
        "sources_failed": sources_fail,
        "count": len(all_items),
        "items": all_items,
    }

    if not all_items:
        output["error"] = "All sources failed. SKILL.md should fall back to WebSearch."

    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
