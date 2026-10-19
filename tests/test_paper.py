"""
Unit tests cho Paper model trong models/paper.py.
Kiểm tra các giá trị mặc định, phương thức to_dict/from_dict, to_excel_row (đúng 17 cột),
và trường mới 'analyzed'.
"""

import pytest
from models.paper import Paper


def test_paper_default_values() -> None:
    """Kiểm tra các giá trị khởi tạo mặc định của Paper, đặc biệt là analyzed=False."""
    paper = Paper()
    assert paper.title == ""
    assert paper.authors == []
    assert paper.year is None
    assert paper.journal == ""
    assert paper.doi == ""
    assert paper.url == ""
    assert paper.citations == 0
    assert paper.abstract == ""
    assert paper.source == ""
    assert paper.relevance_score == 0
    assert paper.relevance_reason == ""
    assert paper.summary == ""
    assert paper.methodology == ""
    assert paper.data_source == ""
    assert paper.key_findings == ""
    assert paper.limitations == ""
    assert paper.policy_implications == ""
    assert paper.notes == ""
    assert paper.analyzed is False


def test_paper_custom_analyzed() -> None:
    """Kiểm tra khởi tạo Paper với trường analyzed=True."""
    paper = Paper(title="Kinh tế số", analyzed=True)
    assert paper.title == "Kinh tế số"
    assert paper.analyzed is True


def test_to_dict_includes_analyzed() -> None:
    """Kiểm tra to_dict trả về đủ tất cả các trường bao gồm analyzed."""
    paper = Paper(
        title="Nghiên cứu lạm phát",
        authors=["Nguyễn Văn A", "Trần Thị B"],
        year=2024,
        analyzed=True,
    )
    d = paper.to_dict()
    assert isinstance(d, dict)
    assert d["title"] == "Nghiên cứu lạm phát"
    assert d["authors"] == ["Nguyễn Văn A", "Trần Thị B"]
    assert d["year"] == 2024
    assert d["analyzed"] is True
    assert "analyzed" in d


def test_from_dict_with_analyzed() -> None:
    """Kiểm tra from_dict khôi phục đúng trường analyzed khi có trong dict."""
    data = {
        "title": "Chính sách tiền tệ",
        "authors": ["Lê Văn C"],
        "year": 2023,
        "analyzed": True,
    }
    paper = Paper.from_dict(data)
    assert paper.title == "Chính sách tiền tệ"
    assert paper.authors == ["Lê Văn C"]
    assert paper.year == 2023
    assert paper.analyzed is True


def test_from_dict_without_analyzed_defaults_false() -> None:
    """Kiểm tra from_dict khi thiếu trường analyzed thì mặc định là False."""
    data = {
        "title": "Tăng trưởng xanh",
        "authors": "Tác giả 1, Tác giả 2",
        "year": "2022",
    }
    paper = Paper.from_dict(data)
    assert paper.title == "Tăng trưởng xanh"
    assert paper.authors == ["Tác giả 1", "Tác giả 2"]
    assert paper.year == 2022
    assert paper.analyzed is False


def test_to_excel_row_exactly_18_columns() -> None:
    """Kiểm tra to_excel_row trả về đúng 18 cột và không chứa trường analyzed."""
    paper = Paper(
        title="Tác động FDI",
        authors=["Nguyễn A"],
        year=2021,
        journal="Tạp chí Kinh tế",
        doi="10.1234/econ.2021",
        url="https://doi.org/10.1234/econ.2021",
        citations=15,
        abstract="Tóm tắt bài báo...",
        source="OpenAlex",
        relevance_score=85,
        relevance_reason="Trùng khớp từ khóa FDI",
        summary="Tóm tắt ngắn gọn",
        methodology="Hồi quy OLS",
        data_source="World Bank 2000-2020",
        key_findings="FDI có tác động tích cực",
        limitations="Dữ liệu giới hạn ở một số tỉnh thành",
        policy_implications="Cần thu hút FDI chất lượng cao",
        notes="Bài báo đáng chú ý",
        analyzed=True,
    )
    row = paper.to_excel_row()
    assert isinstance(row, dict)
    assert len(row) == 18, f"Kỳ vọng 18 cột, nhưng nhận được {len(row)} cột"
    assert "analyzed" not in row
    assert row["Tiêu đề"] == "Tác động FDI"
    assert row["Tác giả"] == "Nguyễn A"
    assert row["Năm xuất bản"] == 2021
    assert row["Tạp chí / Nơi xuất bản"] == "Tạp chí Kinh tế"
    assert row["DOI"] == "10.1234/econ.2021"
    assert row["URL"] == "https://doi.org/10.1234/econ.2021"
    assert row["Số trích dẫn"] == 15
    assert row["Nguồn"] == "OpenAlex"
    assert row["Abstract"] == "Tóm tắt bài báo..."
    assert row["Điểm phù hợp"] == 85
    assert row["Lý do phù hợp"] == "Trùng khớp từ khóa FDI"
    assert row["Tóm tắt"] == "Tóm tắt ngắn gọn"
    assert row["Phương pháp"] == "Hồi quy OLS"
    assert row["Dữ liệu nghiên cứu"] == "World Bank 2000-2020"
    assert row["Kết quả chính"] == "FDI có tác động tích cực"
    assert row["Hạn chế"] == "Dữ liệu giới hạn ở một số tỉnh thành"
    assert row["Hàm ý chính sách"] == "Cần thu hút FDI chất lượng cao"
    assert row["Ghi chú"] == "Bài báo đáng chú ý"


def test_roundtrip_serialization() -> None:
    """Kiểm tra chu trình tuần hoàn Paper -> to_dict -> from_dict -> Paper."""
    original = Paper(
        title="Thương mại quốc tế",
        authors=["Tác giả A", "Tác giả B"],
        year=2020,
        journal="Journal of Economics",
        doi="10.1000/182",
        url="https://example.com",
        citations=42,
        abstract="Nội dung tóm tắt",
        source="Semantic Scholar",
        relevance_score=90,
        relevance_reason="Rất phù hợp",
        summary="Tóm lược",
        methodology="Mô hình trọng lực",
        data_source="UN Comtrade",
        key_findings="Xuất khẩu tăng",
        limitations="Mẫu nghiên cứu chưa bao quát các vùng sâu vùng xa",
        policy_implications="Mở rộng thị trường",
        notes="Quan trọng",
        analyzed=True,
    )
    d = original.to_dict()
    reconstructed = Paper.from_dict(d)
    assert original == reconstructed
    assert reconstructed.analyzed is True
