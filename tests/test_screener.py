"""
Unit tests cho ai_analysis/screener.py bằng mock.
Kiểm tra:
- Ghép đúng điểm theo i khi AI trả sai thứ tự
- Bài AI bỏ sót tự động gán điểm 0 và ghi log
- Điểm vượt ngưỡng ngoài [0, 100] được cắt về khoảng hợp lệ
- Bài không có abstract bị chặn trần NO_ABSTRACT_SCORE_CAP
- Khi AI lỗi: gán relevance_score = None, không ném ngoại lệ
- Chia lô batching chính xác theo CANDIDATE_POOL_SIZE
- Kiểm tra nội dung prompt không chứa DOI hay tác giả
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from ai_analysis.screener import score_papers
from models.paper import Paper


def test_score_papers_unordered_mapping() -> None:
    """Kiểm tra ghép đúng điểm số theo chỉ mục i khi AI trả kết quả lộn xộn."""
    p1 = Paper(title="Bài 1", abstract="Tóm tắt bài 1 đầy đủ")
    p2 = Paper(title="Bài 2", abstract="Tóm tắt bài 2 đầy đủ")
    p3 = Paper(title="Bài 3", abstract="Tóm tắt bài 3 đầy đủ")

    mock_response = {
        "scores": [
            {"i": 3, "s": 92},
            {"i": 1, "s": 75},
            {"i": 2, "s": 88},
        ]
    }

    with patch("ai_analysis.screener.call_llm_json", return_value=mock_response) as mock_call:
        results = score_papers([p1, p2, p3], topic="Kinh tế số")

        assert mock_call.call_count == 1
        assert results[0].relevance_score == 75
        assert results[1].relevance_score == 88
        assert results[2].relevance_score == 92


def test_score_papers_missing_item_gets_zero() -> None:
    """Kiểm tra khi AI bỏ sót một bài thì bài đó được gán điểm 0."""
    p1 = Paper(title="Bài A", abstract="Tóm tắt A")
    p2 = Paper(title="Bài B (bị bỏ sót)", abstract="Tóm tắt B")
    p3 = Paper(title="Bài C", abstract="Tóm tắt C")

    mock_response = {
        "scores": [
            {"i": 1, "s": 85},
            {"i": 3, "s": 90},
        ]
    }

    with patch("ai_analysis.screener.call_llm_json", return_value=mock_response):
        results = score_papers([p1, p2, p3], topic="Tăng trưởng xanh")
        assert results[0].relevance_score == 85
        assert results[1].relevance_score == 0
        assert results[2].relevance_score == 90


def test_score_papers_clamping_out_of_bounds() -> None:
    """Kiểm tra điểm ngoài khoảng 0-100 được cắt về [0, 100]."""
    p1 = Paper(title="Bài điểm quá cao", abstract="Tóm tắt 1")
    p2 = Paper(title="Bài điểm âm", abstract="Tóm tắt 2")

    mock_response = {
        "scores": [
            {"i": 1, "s": 150},
            {"i": 2, "s": -25},
        ]
    }

    with patch("ai_analysis.screener.call_llm_json", return_value=mock_response):
        results = score_papers([p1, p2], topic="Chính sách tiền tệ")
        assert results[0].relevance_score == 100
        assert results[1].relevance_score == 0


def test_score_papers_no_abstract_score_capped() -> None:
    """Kiểm tra bài không có abstract bị chặn trần NO_ABSTRACT_SCORE_CAP (mặc định 60)."""
    p_no_abs = Paper(title="Bài không có abstract", abstract="")
    p_has_abs = Paper(title="Bài có abstract", abstract="Đây là abstract hoàn chỉnh...")

    mock_response = {
        "scores": [
            {"i": 1, "s": 95},
            {"i": 2, "s": 95},
        ]
    }

    with patch("ai_analysis.screener.call_llm_json", return_value=mock_response):
        results = score_papers([p_no_abs, p_has_abs], topic="Xuất khẩu dịch vụ")
        assert results[0].relevance_score == 60  # Bị chặn trần 60
        assert results[1].relevance_score == 95  # Không bị chặn


def test_score_papers_llm_exception_sets_none_no_crash() -> None:
    """Kiểm tra khi LLM lỗi thì đặt relevance_score = None và không làm app bị dừng/crash."""
    p1 = Paper(title="Bài 1", abstract="Tóm tắt 1")
    p2 = Paper(title="Bài 2", abstract="Tóm tắt 2")

    with patch(
        "ai_analysis.screener.call_llm_json",
        side_effect=RuntimeError("Mất kết nối API"),
    ):
        results = score_papers([p1, p2], topic="Đề tài lỗi mạng")
        assert results[0].relevance_score is None
        assert results[1].relevance_score is None


def test_score_papers_batching(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra chia lô theo CANDIDATE_POOL_SIZE (ví dụ 2 bài/lô)."""
    monkeypatch.setattr("config.settings.CANDIDATE_POOL_SIZE", 2)

    papers = [Paper(title=f"Bài {i}", abstract=f"Tóm tắt {i}") for i in range(1, 6)]

    def mock_call(prompt: str, **kwargs: Any) -> dict:
        return {"scores": [{"i": 1, "s": 80}, {"i": 2, "s": 85}]}

    with patch("ai_analysis.screener.call_llm_json", side_effect=mock_call) as mock_func:
        results = score_papers(papers, topic="Batching test")
        # 5 bài chia 2 bài/lô -> 3 lần gọi
        assert mock_func.call_count == 3
        assert len(results) == 5


def test_score_papers_prompt_content() -> None:
    """Kiểm tra prompt gửi AI có đúng câu bắt buộc và không chứa DOI hay tác giả."""
    p = Paper(
        title="Nghiên cứu tác động FDI",
        authors=["Nguyen Van A", "Tran Thi B"],
        doi="10.1000/econ.test",
        year=2023,
        abstract="Tóm tắt nghiên cứu FDI tại Việt Nam...",
    )

    captured_prompt: list[str] = []

    def mock_call(prompt: str, **kwargs: Any) -> dict:
        captured_prompt.append(prompt)
        return {"scores": [{"i": 1, "s": 80}]}

    with patch("ai_analysis.screener.call_llm_json", side_effect=mock_call):
        topic = "FDI và tăng trưởng kinh tế"
        score_papers([p], topic=topic)

        assert len(captured_prompt) == 1
        prompt_text = captured_prompt[0]

        # Kiểm tra câu bắt buộc
        expected_phrase = f"Chỉ dùng thông tin trong văn bản được cung cấp. Không bịa. Chấm mức phù hợp với đề tài nghiên cứu: {topic}."
        assert expected_phrase in prompt_text

        # Kiểm tra không chứa DOI hay tác giả
        assert "10.1000/econ.test" not in prompt_text
        assert "Nguyen Van A" not in prompt_text
        assert "Tran Thi B" not in prompt_text
