"""
Unit tests cho ai_analysis/roadmap_builder.py.
Kiểm tra:
- Khởi tạo fallback roadmap khi không có đề tài hoặc gặp lỗi AI
- Làm sạch và chuẩn hóa mã Mermaid
- Sinh roadmap thành công với mock response từ AI
- Trích xuất đúng cấu trúc các phase và steps
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from ai_analysis.roadmap_builder import (
    _build_fallback_roadmap,
    _sanitize_mermaid_code,
    generate_research_roadmap,
)
from models.paper import Paper


def test_sanitize_mermaid_code() -> None:
    """Kiểm tra hàm chuẩn hóa mã Mermaid loại bỏ markdown code fences."""
    raw = "```mermaid\ngraph TD\nA-->B\n```"
    sanitized = _sanitize_mermaid_code(raw)
    assert not sanitized.startswith("```")
    assert "A-->B" in sanitized
    assert sanitized.startswith("graph ") or sanitized.startswith("flowchart ")

    # Tự thêm flowchart TD nếu thiếu
    plain = "A[\"Giai đoạn 1\"] --> B[\"Giai đoạn 2\"]"
    auto_flow = _sanitize_mermaid_code(plain)
    assert auto_flow.startswith("flowchart TD")


def test_build_fallback_roadmap() -> None:
    """Kiểm tra fallback roadmap tạo cấu trúc đầy đủ các giai đoạn chuẩn mực NCKH."""
    topic = "Tác động của Fintech đến hiệu quả ngân hàng"
    fb = _build_fallback_roadmap(topic, "Định lượng (Quantitative)")

    assert fb["topic"] == topic
    assert fb["research_type"] == "Định lượng (Quantitative)"
    assert len(fb["phases"]) >= 4
    assert len(fb["research_questions"]) >= 3
    assert "flowchart TD" in fb["mermaid_code"]

    # Kiểm tra các bước trong giai đoạn 1
    p1 = fb["phases"][0]
    assert len(p1["steps"]) >= 2
    step1 = p1["steps"][0]
    assert "id" in step1
    assert "title" in step1
    assert "tasks" in step1
    assert "deliverable" in step1


def test_generate_roadmap_with_empty_topic() -> None:
    """Kiểm tra khi đề tài rỗng thì trả về fallback an toàn mà không gọi AI."""
    res = generate_research_roadmap("")
    assert res is not None
    assert "phases" in res
    assert len(res["phases"]) >= 4


def test_generate_roadmap_mocked_llm() -> None:
    """Kiểm tra khi AI trả về JSON hợp lệ thì parse đúng cấu trúc."""
    mock_ai_json = {
        "topic": "Chuyển đổi số",
        "research_type": "Định lượng",
        "overview": "Mô tả tổng quan hướng đi nghiên cứu.",
        "research_questions": ["Câu hỏi 1", "Câu hỏi 2"],
        "mermaid_code": "graph TD\nP1 --> P2",
        "phases": [
            {
                "phase_id": "P1",
                "phase_name": "Giai đoạn 1: Khởi động",
                "description": "Tổng quan lý thuyết",
                "steps": [
                    {
                        "id": "step_1_1",
                        "title": "Xác định khoảng trống",
                        "tasks": "Đọc 30 bài báo",
                        "deliverable": "Chương 1",
                        "tools_tips": "Zotero",
                    }
                ],
            }
        ],
    }

    paper_mock = Paper(title="Fintech in Banking", methodology="GMM Panel Data", data_source="50 Banks")

    with patch("ai_analysis.roadmap_builder.call_llm_json", return_value=mock_ai_json):
        result = generate_research_roadmap(
            topic="Chuyển đổi số",
            research_type="Định lượng",
            papers=[paper_mock],
            use_cache=False,
        )

        assert result["topic"] == "Chuyển đổi số"
        assert len(result["phases"]) == 1
        assert result["phases"][0]["phase_name"] == "Giai đoạn 1: Khởi động"
        assert result["phases"][0]["steps"][0]["id"] == "step_1_1"


def test_generate_roadmap_exception_fallback() -> None:
    """Kiểm tra khi AI văng Exception (hết quota, lỗi mạng) thì tự động kích hoạt fallback an toàn."""
    with patch("ai_analysis.roadmap_builder.call_llm_json", side_effect=RuntimeError("Quota exceeded")):
        res = generate_research_roadmap("Chính sách tiền tệ", use_cache=False)
        assert res is not None
        assert res["topic"] == "Chính sách tiền tệ"
        assert len(res["phases"]) >= 4
