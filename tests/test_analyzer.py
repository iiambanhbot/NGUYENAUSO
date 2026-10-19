"""
Unit tests cho ai_analysis/analyzer.py bằng mock.
Kiểm tra:
- Ghép đúng theo i dù AI trả lộn xộn thứ tự
- Bài không có abstract KHÔNG bị gửi cho AI, đặt basis='none', analyzed=True
- Cache riêng biệt theo từng bài (bài đã có cache thì không gửi lại)
- Thử lại đúng 1 lần cho những bài bị bỏ sót
- Trường thiếu trả về None hoặc [] đúng yêu cầu
- Lỗi AI không làm crash app, đặt analyzed=False
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ai_analysis.analyzer import analyze_papers
from models.paper import Paper


@pytest.fixture(autouse=True)
def setup_test_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Cấu hình cache tạm cho test analyzer."""
    cache_dir = tmp_path / "test_analyzer_cache"
    monkeypatch.setattr("config.settings.CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    return cache_dir


def test_analyze_papers_matching_by_i() -> None:
    """Kiểm tra ánh xạ kết quả phân tích đúng theo chỉ số i khi AI trả kết quả bị đảo thứ tự."""
    p1 = Paper(doi="10.1000/p1", title="Bài 1", year=2021, abstract="Abstract của bài số 1")
    p2 = Paper(doi="10.1000/p2", title="Bài 2", year=2022, abstract="Abstract của bài số 2")

    mock_llm_response = [
        {
            "i": 2,
            "short_summary": "Tóm tắt ngắn bài 2.",
            "detail_summary": "Chi tiết bài 2 liên quan đến tăng trưởng xanh.",
            "method": "OLS",
            "sample": "100 doanh nghiệp",
            "variables": ["doanh thu", "chi phí"],
            "countries": ["Việt Nam"],
            "main_findings": "Tăng trưởng tích cực",
        },
        {
            "i": 1,
            "short_summary": "Tóm tắt ngắn bài 1.",
            "detail_summary": "Chi tiết bài 1 liên quan đến chuyển đổi số.",
            "method": "GMM",
            "sample": "50 ngân hàng",
            "variables": ["vốn", "tín dụng"],
            "countries": ["ASEAN"],
            "main_findings": "Chuyển đổi số cải thiện hiệu quả",
            "limitations": "Cỡ mẫu nhỏ, chỉ giới hạn khối ngân hàng",
        },
    ]

    with patch("ai_analysis.analyzer.call_llm_json", return_value=mock_llm_response) as mock_call:
        results = analyze_papers([p1, p2], topic="Kinh tế số và tăng trưởng")

        assert mock_call.call_count == 1

        assert results[0].analyzed is True
        assert results[0].summary == "Tóm tắt ngắn bài 1."
        assert results[0].detail_summary == "Chi tiết bài 1 liên quan đến chuyển đổi số."
        assert results[0].methodology == "GMM"
        assert results[0].limitations == "Cỡ mẫu nhỏ, chỉ giới hạn khối ngân hàng"
        assert results[0].extracted_data.limitations == "Cỡ mẫu nhỏ, chỉ giới hạn khối ngân hàng"
        assert results[0].extracted_data.basis == "abstract"
        assert results[0].extracted_data.variables == ["vốn", "tín dụng"]

        assert results[1].analyzed is True
        assert results[1].summary == "Tóm tắt ngắn bài 2."
        assert results[1].methodology == "OLS"


def test_paper_without_abstract_not_sent() -> None:
    """Kiểm tra bài không có abstract KHÔNG được gửi cho AI và được gắn cờ basis='none'."""
    p_with_abs = Paper(doi="10.1000/with_abs", title="Có abstract", abstract="Abstract hợp lệ")
    p_no_abs = Paper(doi="10.1000/no_abs", title="Không abstract", abstract="")

    mock_llm_response = [
        {
            "i": 1,
            "short_summary": "Tóm tắt bài có abstract.",
            "detail_summary": "Chi tiết bài có abstract.",
            "method": "Case study",
            "sample": None,
            "variables": [],
            "countries": [],
            "main_findings": "Kết quả tốt",
        }
    ]

    captured_prompt: list[str] = []

    def mock_call(prompt: str, **kwargs: Any) -> Any:
        captured_prompt.append(prompt)
        return mock_llm_response

    with patch("ai_analysis.analyzer.call_llm_json", side_effect=mock_call):
        results = analyze_papers([p_with_abs, p_no_abs], topic="Phân tích mẫu")

        # Kiểm tra nội dung gửi AI chỉ có bài có abstract
        assert len(captured_prompt) == 1
        assert "Có abstract" in captured_prompt[0]
        assert "Không abstract" not in captured_prompt[0]

        # Kiểm tra bài không có abstract
        assert p_no_abs.analyzed is True
        assert p_no_abs.summary == "Không có abstract để tóm tắt"
        assert p_no_abs.extracted_data.basis == "none"

        # Kiểm tra bài có abstract
        assert p_with_abs.analyzed is True
        assert p_with_abs.summary == "Tóm tắt bài có abstract."
        assert p_with_abs.extracted_data.basis == "abstract"


def test_cache_per_paper() -> None:
    """Kiểm tra cache theo từng bài báo: bài đã phân tích thì lần sau không gửi lại."""
    p1 = Paper(doi="10.1000/cache1", title="Bài 1", abstract="Abstract bài 1")
    p2 = Paper(doi="10.1000/cache2", title="Bài 2", abstract="Abstract bài 2")

    mock_resp_1 = [
        {"i": 1, "short_summary": "Tóm tắt 1", "detail_summary": "Chi tiết 1", "method": "M1"}
    ]
    mock_resp_2 = [
        {"i": 1, "short_summary": "Tóm tắt 2", "detail_summary": "Chi tiết 2", "method": "M2"}
    ]

    with patch("ai_analysis.analyzer.call_llm_json", side_effect=[mock_resp_1, mock_resp_2]) as mock_call:
        # Lần 1: Phân tích bài 1
        analyze_papers([p1], topic="Chủ đề cache")
        assert mock_call.call_count == 1
        assert p1.summary == "Tóm tắt 1"

        # Lần 2: Phân tích lại bài 1 -> Trúng cache, không gọi mạng
        analyze_papers([p1], topic="Chủ đề cache")
        assert mock_call.call_count == 1  # Không tăng

        # Lần 3: Gửi cả bài 1 (đã cache) và bài 2 (chưa cache) -> Chỉ gửi bài 2
        analyze_papers([p1, p2], topic="Chủ đề cache")
        assert mock_call.call_count == 2
        assert p2.summary == "Tóm tắt 2"


def test_retry_missing_papers() -> None:
    """Kiểm tra khi AI bỏ sót bài thì tự động gọi lại 1 lần chỉ cho bài bị sót."""
    p1 = Paper(doi="10.1000/r1", title="Bài 1", abstract="Abstract 1")
    p2 = Paper(doi="10.1000/r2", title="Bài 2 (bị bỏ sót lần 1)", abstract="Abstract 2")

    # Lần 1: AI chỉ trả bài 1 (bỏ sót bài 2)
    resp_batch_1 = [
        {"i": 1, "short_summary": "Tóm tắt 1", "detail_summary": "Chi tiết 1"}
    ]

    # Lần 2 (thử lại): AI trả cho bài 2 (được đánh chỉ số 1 trong batch retry)
    resp_batch_2 = [
        {"i": 1, "short_summary": "Tóm tắt 2 (đã bổ sung)", "detail_summary": "Chi tiết 2"}
    ]

    with patch("ai_analysis.analyzer.call_llm_json", side_effect=[resp_batch_1, resp_batch_2]) as mock_call:
        results = analyze_papers([p1, p2], topic="Chủ đề retry")
        assert mock_call.call_count == 2
        assert results[0].analyzed is True
        assert results[0].summary == "Tóm tắt 1"
        assert results[1].analyzed is True
        assert results[1].summary == "Tóm tắt 2 (đã bổ sung)"


def test_missing_fields_default_to_none_or_empty_list() -> None:
    """Kiểm tra các trường thiếu hoặc null trong JSON phản hồi trả về None hoặc []."""
    p = Paper(doi="10.1000/missing_f", title="Bài thiếu trường", abstract="Abstract ngắn")

    mock_resp = [
        {
            "i": 1,
            "short_summary": "Tóm tắt tối giản",
            "detail_summary": "Chi tiết tối giản",
            "method": None,
            "sample": None,
            "variables": None,
            "countries": [],
            "main_findings": None,
        }
    ]

    with patch("ai_analysis.analyzer.call_llm_json", return_value=mock_resp):
        results = analyze_papers([p], topic="Chủ đề test")
        data = results[0].extracted_data
        assert data.method is None
        assert data.sample is None
        assert data.main_findings is None
        assert data.limitations is None
        assert data.variables == []
        assert data.countries == []


def test_llm_error_sets_analyzed_false_no_crash() -> None:
    """Kiểm tra khi LLM lỗi thì đặt analyzed=False và không làm sập ứng dụng."""
    p = Paper(doi="10.1000/err", title="Bài lỗi mạng", abstract="Abstract test")

    with patch(
        "ai_analysis.analyzer.call_llm_json",
        side_effect=RuntimeError("Mất kết nối API"),
    ):
        results = analyze_papers([p], topic="Lỗi")
        assert len(results) == 1
        assert results[0].analyzed is False
