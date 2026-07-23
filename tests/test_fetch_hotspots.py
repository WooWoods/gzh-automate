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
