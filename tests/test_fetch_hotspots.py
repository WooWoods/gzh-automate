"""Tests for fetch_hotspots module."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure src/ is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from wewrite.commands.fetch_hotspots import (
    fetch_unified,
    fetch_zhihu,
    fetch_bilibili,
    deduplicate,
)


class TestFetchUnified:
    """Tests for the unified API fetcher."""

    def test_returns_items_on_valid_response(self):
        """Valid JSON response with data array produces item list."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "code": 200,
            "data": [
                {"id": 1, "title": "测试话题", "hot": "1234567",
                 "url": "https://example.com/1"},
                {"id": 2, "title": "另一个话题", "hot": "890123",
                 "url": "https://example.com/2"},
            ],
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_unified("test_platform")

        assert len(items) == 2
        assert items[0]["title"] == "测试话题"
        assert items[0]["source"] == "test_platform"
        assert items[0]["hot"] == 1234567
        assert items[0]["url"] == "https://example.com/1"
        assert items[0]["description"] == ""
        assert items[1]["title"] == "另一个话题"

    def test_preserves_platform_name_label(self):
        """Platform label is passed through to source field."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "code": 200,
            "data": [{"id": 1, "title": "话题", "hot": "100", "url": ""}],
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_unified("test_platform")

        assert items[0]["source"] == "test_platform"

    def test_skips_items_with_empty_title(self):
        """Items with empty or missing title are filtered out."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "code": 200,
            "data": [
                {"id": 1, "title": "", "hot": "100", "url": ""},
                {"id": 2, "title": "有效话题", "hot": "200", "url": ""},
                {"id": 3, "hot": "300", "url": ""},  # no title key
            ],
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_unified("test_platform")

        assert len(items) == 1
        assert items[0]["title"] == "有效话题"

    def test_returns_empty_list_on_http_failure(self):
        """Network / HTTP errors return [] — never raise."""
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            side_effect=Exception("Connection refused"),
        ):
            items = fetch_unified("test_platform")

        assert items == []

    def test_returns_empty_list_on_malformed_json(self):
        """Non-dict / missing data key returns []."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = ["not", "a", "dict"]
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_unified("test_platform")

        assert items == []

    def test_normalizes_heat_strings(self):
        """Heat values like '123.4万' are parsed to integers."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "code": 200,
            "data": [
                {"id": 1, "title": "话题A", "hot": "123.4万", "url": ""},
                {"id": 2, "title": "话题B", "hot": "1.2亿", "url": ""},
                {"id": 3, "title": "话题C", "hot": 5678, "url": ""},
            ],
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_unified("test_platform")

        assert items[0]["hot"] == 1234000   # 123.4万
        assert items[1]["hot"] == 120000000  # 1.2亿
        assert items[2]["hot"] == 5678        # raw int


class TestFetchZhihu:
    """Tests for the Zhihu native API fetcher."""

    def test_parses_zhihu_hot_list(self):
        """Valid Zhihu API response produces items with correct fields."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {
                    "target": {
                        "id": 123456,
                        "title": "如何看待AI发展？",
                        "excerpt": "AI正在改变世界...",
                    },
                    "detail_text": "1000 万热度",
                },
                {
                    "target": {
                        "id": 789012,
                        "title": "2025年经济展望",
                        "excerpt": "经济学家预测...",
                    },
                    "detail_text": "800 万热度",
                },
            ]
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_zhihu()

        assert len(items) == 2
        assert items[0]["title"] == "如何看待AI发展？"
        assert items[0]["source"] == "知乎"
        assert items[0]["url"] == "https://www.zhihu.com/question/123456"
        assert items[0]["description"] == "AI正在改变世界..."
        assert items[1]["title"] == "2025年经济展望"

    def test_skips_items_with_empty_title(self):
        """Items with empty target.title are filtered out."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {
                    "target": {"id": 1, "title": "", "excerpt": ""},
                    "detail_text": "100 万热度",
                },
                {
                    "target": {"id": 2, "title": "有效问题", "excerpt": ""},
                    "detail_text": "200 万热度",
                },
            ]
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_zhihu()

        assert len(items) == 1
        assert items[0]["title"] == "有效问题"

    def test_returns_empty_list_on_failure(self):
        """Network error returns [] gracefully."""
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            side_effect=Exception("Timeout"),
        ):
            items = fetch_zhihu()
        assert items == []


class TestFetchBilibili:
    """Tests for the Bilibili native API fetcher."""

    def test_parses_bilibili_popular_list(self):
        """Valid Bilibili API response produces items with correct fields."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "list": [
                    {
                        "title": "【4K】绝美风景",
                        "bvid": "BV1xx411c7mD",
                        "tname": "旅游",
                        "stat": {"view": 1234567, "like": 89012, "reply": 3456},
                    },
                    {
                        "title": "2025最新科技解读",
                        "bvid": "BV2yy522d8nE",
                        "tname": "科技",
                        "stat": {"view": 987654, "like": 76543, "reply": 2109},
                    },
                ]
            }
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_bilibili()

        assert len(items) == 2
        assert items[0]["title"] == "【4K】绝美风景"
        assert items[0]["source"] == "B站"
        assert items[0]["hot"] == 1234567
        assert items[0]["url"] == "https://www.bilibili.com/video/BV1xx411c7mD"
        assert items[0]["description"] == "旅游"
        assert items[1]["title"] == "2025最新科技解读"

    def test_skips_items_with_empty_title(self):
        """Items with empty title are filtered out."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "list": [
                    {"title": "", "bvid": "BVxxx", "tname": "",
                     "stat": {"view": 100}},
                    {"title": "有效视频", "bvid": "BVyyy", "tname": "科技",
                     "stat": {"view": 200}},
                ]
            }
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_bilibili()

        assert len(items) == 1
        assert items[0]["title"] == "有效视频"

    def test_returns_empty_list_on_failure(self):
        """Network error returns [] gracefully."""
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            side_effect=Exception("Timeout"),
        ):
            items = fetch_bilibili()
        assert items == []

    def test_handles_missing_stat_key(self):
        """Response without stat.view uses 0 as heat."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {
                "list": [
                    {"title": "无统计数据", "bvid": "BVzzz", "tname": "",
                     "stat": {}},
                ]
            }
        }
        with patch(
            "wewrite.commands.fetch_hotspots._request_with_retry",
            return_value=mock_resp,
        ):
            items = fetch_bilibili()

        assert len(items) == 1
        assert items[0]["hot"] == 0


class TestCompositeFetchers:
    """Tests for composite (unified -> native fallback) fetchers."""

    def test_fetch_zhihu_composite_unified_succeeds(self):
        """When unified API works, its result is used directly."""
        from wewrite.commands.fetch_hotspots import _fetch_with_fallback

        def unified_ok():
            return [{"title": "知乎热点", "source": "知乎", "hot": 100,
                     "url": "", "description": ""}]

        def native():
            return [{"title": "不应该被调用", "source": "知乎", "hot": 999,
                     "url": "", "description": ""}]

        items = _fetch_with_fallback("zhihu", unified_ok, native)
        assert len(items) == 1
        assert items[0]["hot"] == 100

    def test_fetch_zhihu_composite_unified_fails_falls_back(self):
        """When unified API returns [], native API is used instead."""
        from wewrite.commands.fetch_hotspots import _fetch_with_fallback

        def unified_empty():
            return []

        def native():
            return [{"title": "知乎原生热点", "source": "知乎", "hot": 200,
                     "url": "", "description": ""}]

        items = _fetch_with_fallback("zhihu", unified_empty, native)
        assert len(items) == 1
        assert items[0]["hot"] == 200
        assert items[0]["title"] == "知乎原生热点"

    def test_fetch_with_fallback_both_fail(self):
        """When both tiers fail, returns [] gracefully."""
        from wewrite.commands.fetch_hotspots import _fetch_with_fallback

        def fail1():
            raise Exception("unified down")

        def fail2():
            raise Exception("native down")

        items = _fetch_with_fallback("test", fail1, fail2)
        assert items == []


class TestParseHeatValue:
    """Tests for _parse_heat_value edge cases."""

    def test_parses_wan_heat_suffix_format(self):
        """Heat strings like '1000 万热度' are parsed after stripping '热度' suffix."""
        from wewrite.commands.fetch_hotspots import _parse_heat_value

        assert _parse_heat_value("1000 万热度") == 10000000
        assert _parse_heat_value("800 万热度") == 8000000

    def test_parses_stripped_suffixes(self):
        """Common suffixes (热度, 讨论, 阅读) are stripped before parsing."""
        from wewrite.commands.fetch_hotspots import _parse_heat_value

        assert _parse_heat_value("500 万讨论") == 5000000
        assert _parse_heat_value("300 万阅读") == 3000000


class TestFullPipeline:
    """Integration-style tests for the full hotspot pipeline."""

    def test_all_fetchers_in_main_dict(self):
        """All 10 platform fetchers are registered."""
        import wewrite.commands.fetch_hotspots as fh

        expected = [
            "fetch_weibo", "fetch_toutiao", "fetch_baidu",
            "fetch_zhihu", "fetch_bilibili",
            "fetch_douyin", "fetch_douban",
            "fetch_thepaper", "fetch_36kr", "fetch_ithome",
        ]
        for name in expected:
            assert hasattr(fh, name), f"Missing fetcher: {name}"
            assert callable(getattr(fh, name)), f"{name} is not callable"

    def test_deduplicate_removes_exact_title_duplicates(self):
        """Exact title matches are deduplicated, keeping first occurrence."""
        items = [
            {"title": "  AI改变世界 ", "source": "微博", "hot": 100,
             "url": "", "description": ""},
            {"title": "AI改变世界", "source": "知乎", "hot": 200,
             "url": "", "description": ""},
            {"title": "另一话题", "source": "百度", "hot": 50,
             "url": "", "description": ""},
        ]
        result = deduplicate(items)
        assert len(result) == 2
        # First occurrence wins (微博), after strip normalization
        assert result[0]["source"] == "微博"

    def test_deduplicate_strips_whitespace(self):
        """Titles differing only in surrounding whitespace are duplicates."""
        items = [
            {"title": "话题", "source": "A", "hot": 1,
             "url": "", "description": ""},
            {"title": "  话题  ", "source": "B", "hot": 2,
             "url": "", "description": ""},
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_deduplicate_filters_empty_titles(self):
        """Items with empty title (after strip) are removed."""
        items = [
            {"title": "   ", "source": "A", "hot": 1,
             "url": "", "description": ""},
            {"title": "有效", "source": "B", "hot": 2,
             "url": "", "description": ""},
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert result[0]["title"] == "有效"

    @patch("wewrite.commands.fetch_hotspots.fetch_weibo", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_toutiao", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_baidu", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_zhihu", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_bilibili", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_douyin", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_douban", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_thepaper", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_36kr", return_value=[])
    @patch("wewrite.commands.fetch_hotspots.fetch_ithome",
           return_value=[{"title": "IT之家测试",
                          "source": "IT之家", "hot": 5000,
                          "url": "https://ithome.com", "description": ""}])
    @patch("wewrite.commands.fetch_hotspots.fetch_unified", return_value=[])
    @patch("sys.argv", ["fetch_hotspots.py"])
    def test_pipeline_gracefully_handles_all_failures(
        self, *mocks,
    ):
        """When most fetchers fail, the pipeline still produces output."""
        import io

        from wewrite.commands.fetch_hotspots import main as hotspot_main

        # Capture stdout
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            hotspot_main()

        output = json.loads(stdout.getvalue())
        assert "timestamp" in output
        assert "sources" in output
        assert "sources_failed" in output
        assert "count" in output
        assert output["count"] >= 1
        # The one working source should appear
        assert "ithome" in output["sources"]
        # Verify the item data came through
        assert any(item["source"] == "IT之家" for item in output["items"])
