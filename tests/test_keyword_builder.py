"""
Unit tests cho query/keyword_builder.py bằng mock.
Kiểm tra:
- Đúng 1 lần gọi call_llm_json với max_output_tokens=400
- Cấu trúc trả về đúng chuẩn: primary_en, en, vi
- Khi call_llm_json lỗi thì tự động dùng phương án dự phòng an toàn, không ném lỗi
- Xử lý đề tài rỗng an toàn
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from query.keyword_builder import build_keywords


def test_build_keywords_success() -> None:
    """Kiểm tra gọi call_llm_json thành công và trả về đúng định dạng từ khóa song ngữ."""
    mock_llm_output = {
        "primary_en": "digital ecosystem tourism services export",
        "en": [
            "smart tourism digital platform",
            "tourism services trade international",
        ],
        "vi": [
            "hệ sinh thái số du lịch",
            "xuất khẩu dịch vụ du lịch",
        ],
    }

    with patch("query.keyword_builder.call_llm_json", return_value=mock_llm_output) as mock_call:
        topic = "hệ sinh thái số và xuất khẩu dịch vụ du lịch"
        result = build_keywords(topic)

        assert mock_call.call_count == 1
        _, kwargs = mock_call.call_args
        assert kwargs["max_output_tokens"] == 400

        assert isinstance(result, dict)
        assert result["primary_en"] == "digital ecosystem tourism services export"
        assert len(result["en"]) == 2
        assert len(result["vi"]) == 2
        assert "hệ sinh thái số du lịch" in result["vi"]


def test_build_keywords_fallback_on_exception() -> None:
    """Kiểm tra khi call_llm_json bị lỗi thì trả về fallback mà không ném exception."""
    with patch(
        "query.keyword_builder.call_llm_json",
        side_effect=RuntimeError("Mất kết nối API"),
    ) as mock_call:
        topic = "kinh tế tuần hoàn nông nghiệp"
        result = build_keywords(topic)

        assert mock_call.call_count == 1
        assert isinstance(result, dict)
        assert result["primary_en"] == topic
        assert result["en"] == []
        assert result["vi"] == [topic]


def test_build_keywords_fallback_on_non_dict_return() -> None:
    """Kiểm tra khi call_llm_json trả về dữ liệu không phải dict thì tự động fallback."""
    with patch("query.keyword_builder.call_llm_json", return_value=["invalid", "format"]):
        topic = "chính sách tiền tệ"
        result = build_keywords(topic)

        assert result["primary_en"] == topic
        assert result["en"] == []
        assert result["vi"] == [topic]


def test_build_keywords_empty_topic() -> None:
    """Kiểm tra truyền đề tài rỗng thì trả về cấu trúc rỗng mà không gọi LLM."""
    with patch("query.keyword_builder.call_llm_json") as mock_call:
        result = build_keywords("   ")
        assert mock_call.call_count == 0
        assert result == {"primary_en": "", "en": [], "vi": []}
