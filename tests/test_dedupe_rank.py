"""
Unit tests cho merge/dedupe_rank.py.
Kiểm tra các trường hợp:
- Loại trùng lặp theo DOI
- Loại trùng lặp theo tiêu đề + năm xuất bản
- Loại bỏ các bài có trong exclude_keys
- Bổ sung các trường dữ liệu còn thiếu từ bản trùng lặp
- Xếp hạng (rank) theo relevance_score giảm dần và citation_count cho bài chưa chấm điểm
"""

from __future__ import annotations

import pytest
from merge.dedupe_rank import get_dedupe_key, merge, rank
from models.paper import Paper


def test_get_dedupe_key() -> None:
    """Kiểm tra tạo khóa định danh dedupe_key cho bài báo."""
    p1 = Paper(doi="https://doi.org/10.1016/j.econ.2023.01")
    assert p1.dedupe_key == "doi:10.1016/j.econ.2023.01"

    p2 = Paper(title="Digital  Tourism in Vietnam: A Review! ", year=2024)
    assert p2.dedupe_key == "title_year:digital_tourism_in_vietnam_a_review_2024"


def test_merge_dedupe_by_doi() -> None:
    """Kiểm tra gộp các danh sách và loại bỏ trùng lặp theo DOI."""
    p1 = Paper(
        title="Bản OpenAlex",
        doi="https://doi.org/10.1000/182",
        year=2021,
        abstract="Tóm tắt ngắn",
    )
    p2 = Paper(
        title="Bản Semantic Scholar",
        doi="10.1000/182",
        year=2021,
        abstract="Tóm tắt đầy đủ chi tiết hơn nhiều",
    )

    merged = merge(lists=[[p1], [p2]], exclude_keys=set())
    assert len(merged) == 1
    assert merged[0].doi == "10.1000/182"
    # Giữ bản có abstract đầy đủ hơn
    assert merged[0].abstract == "Tóm tắt đầy đủ chi tiết hơn nhiều"


def test_merge_dedupe_by_title_and_year() -> None:
    """Kiểm tra loại trùng theo tiêu đề và năm khi không có DOI."""
    p1 = Paper(
        title="Kinh tế tuần hoàn tại Việt Nam",
        year=2023,
        citations=10,
    )
    p2 = Paper(
        title="kinh tế tuần hoàn tại việt nam",
        year=2023,
        citations=25,
        journal="Tạp chí Môi trường",
    )

    merged = merge(lists=[[p1], [p2]], exclude_keys=set())
    assert len(merged) == 1
    assert merged[0].year == 2023
    assert merged[0].citations == 25
    assert merged[0].journal == "Tạp chí Môi trường"


def test_merge_exclude_keys() -> None:
    """Kiểm tra bỏ qua các bài có khóa trong exclude_keys."""
    p1 = Paper(doi="10.1000/excluded", title="Bài đã hiển thị")
    p2 = Paper(doi="10.1000/included", title="Bài mới")

    exclude = {"doi:10.1000/excluded"}
    merged = merge(lists=[[p1, p2]], exclude_keys=exclude)

    assert len(merged) == 1
    assert merged[0].doi == "10.1000/included"


def test_merge_combines_missing_fields() -> None:
    """Kiểm tra khi trùng lặp, bài đầy đủ hơn được bổ sung các trường còn thiếu từ bài kia."""
    p_with_abstract = Paper(
        title="Nghiên cứu xuất khẩu",
        doi="10.1000/export",
        abstract="Đây là phần abstract chi tiết của nghiên cứu...",
        journal="",  # Thiếu journal
        url="",      # Thiếu URL
        citations=5,
    )

    p_with_metadata = Paper(
        title="Nghiên cứu xuất khẩu",
        doi="10.1000/export",
        abstract="",  # Thiếu abstract
        journal="Journal of International Trade",
        url="https://doi.org/10.1000/export",
        citations=12,
        limitations="Số liệu chỉ lấy từ năm 2015 đến 2020",
        policy_implications="Cần đẩy mạnh xuất khẩu số",
    )
    # Gán thuộc tính mở rộng
    p_with_metadata.open_access_url = "https://example.com/pdf"

    merged = merge(lists=[[p_with_abstract], [p_with_metadata]], exclude_keys=set())
    assert len(merged) == 1
    result = merged[0]

    assert result.doi == "10.1000/export"
    assert result.abstract == "Đây là phần abstract chi tiết của nghiên cứu..."
    assert result.journal == "Journal of International Trade"
    assert result.url == "https://doi.org/10.1000/export"
    assert result.citations == 12
    assert getattr(result, "open_access_url", "") == "https://example.com/pdf"
    assert result.limitations == "Số liệu chỉ lấy từ năm 2015 đến 2020"
    assert result.policy_implications == "Cần đẩy mạnh xuất khẩu số"


def test_rank_order() -> None:
    """Kiểm tra thứ tự xếp hạng: bài có relevance_score xếp trước, bài chưa có điểm xếp sau theo citation_count."""
    p_score_90 = Paper(title="Bài điểm 90", relevance_score=90, citations=5)
    p_score_85 = Paper(title="Bài điểm 85", relevance_score=85, citations=20)
    p_score_85_high_cit = Paper(title="Bài điểm 85 trích dẫn cao", relevance_score=85, citations=100)
    p_unscored_high_cit = Paper(title="Bài chưa chấm điểm trích dẫn cao", relevance_score=0, citations=500)
    p_unscored_low_cit = Paper(title="Bài chưa chấm điểm trích dẫn thấp", relevance_score=0, citations=10)

    papers = [
        p_unscored_low_cit,
        p_score_85,
        p_unscored_high_cit,
        p_score_90,
        p_score_85_high_cit,
    ]

    ranked = rank(papers)

    expected_titles = [
        "Bài điểm 90",
        "Bài điểm 85 trích dẫn cao",
        "Bài điểm 85",
        "Bài chưa chấm điểm trích dẫn cao",
        "Bài chưa chấm điểm trích dẫn thấp",
    ]
    actual_titles = [p.title for p in ranked]
    assert actual_titles == expected_titles


def test_merge_and_rank_empty() -> None:
    """Kiểm tra xử lý danh sách rỗng an toàn không gây lỗi."""
    assert merge([], set()) == []
    assert merge([[]], set()) == []
    assert rank([]) == []
