"""
Unit tests cho sources/openalex.py.
Kiểm tra dựng abstract, chuẩn hóa DOI, ánh xạ trường sang Paper,
cơ chế cache (lần 2 không gọi mạng), và xử lý lỗi mạng / mã lỗi 429, 5xx với retry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests
from models.paper import Paper
from sources.openalex import normalize_doi, reconstruct_abstract, search


@pytest.fixture(autouse=True)
def setup_tmp_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Thiết lập cache tạm thời và mock time.sleep để chạy nhanh không bị delay."""
    cache_dir = tmp_path / "test_openalex_cache"
    monkeypatch.setattr("config.settings.CACHE_DIR", str(cache_dir))
    monkeypatch.setattr("time.sleep", lambda _: None)
    return cache_dir


def test_reconstruct_abstract() -> None:
    """Kiểm tra khôi phục chuỗi văn bản abstract từ inverted index."""
    inverted_index = {
        "This": [0],
        "study": [1],
        "investigates": [2],
        "digital": [3],
        "ecosystem.": [4],
    }
    abstract = reconstruct_abstract(inverted_index)
    assert abstract == "This study investigates digital ecosystem."

    assert reconstruct_abstract(None) == ""
    assert reconstruct_abstract({}) == ""


def test_normalize_doi() -> None:
    """Kiểm tra chuẩn hóa DOI qua hàm và staticmethod Paper.normalize_doi."""
    doi_url = "https://doi.org/10.1016/j.econ.2021.1001"
    normalized = Paper.normalize_doi(doi_url)
    assert normalized == "10.1016/j.econ.2021.1001"

    doi_prefix = "doi:10.1000/182"
    assert normalize_doi(doi_prefix) == "10.1000/182"
    assert normalize_doi("") == ""
    assert normalize_doi(None) == ""


def _create_mock_work_item() -> dict[str, Any]:
    return {
        "id": "https://openalex.org/W123456789",
        "doi": "https://doi.org/10.1000/econ.2023.01",
        "title": "Digital Ecosystem in Tourism",
        "authorships": [
            {"author": {"display_name": "Nguyen Van A"}},
            {"author": {"display_name": "Tran Thi B"}},
        ],
        "publication_year": 2023,
        "primary_location": {
            "source": {"display_name": "Journal of Tourism Economics"},
            "landing_page_url": "https://example.com/paper/1",
        },
        "cited_by_count": 42,
        "open_access": {
            "is_oa": True,
            "oa_url": "https://example.com/paper/1.pdf",
        },
        "abstract_inverted_index": {
            "Digital": [0],
            "transformation": [1],
            "drives": [2],
            "tourism": [3],
            "growth.": [4],
        },
        "language": "en",
    }


def test_search_mapping() -> None:
    """Kiểm tra ánh xạ đầy đủ và chính xác dữ liệu OpenAlex sang đối tượng Paper."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [_create_mock_work_item()]
    }

    with patch("requests.get", return_value=mock_response) as mock_get:
        papers = search(query="digital tourism", year_from=2020, limit=5, page=1)

        assert mock_get.called
        assert len(papers) == 1
        p = papers[0]

        assert isinstance(p, Paper)
        assert p.id == "10.1000/econ.2023.01"  # Ưu tiên DOI chuẩn hóa
        assert p.doi == "10.1000/econ.2023.01"
        assert p.title == "Digital Ecosystem in Tourism"
        assert p.authors == ["Nguyen Van A", "Tran Thi B"]
        assert p.year == 2023
        assert p.venue == "Journal of Tourism Economics"
        assert p.journal == "Journal of Tourism Economics"
        assert p.citation_count == 42
        assert p.citations == 42
        assert p.is_open_access is True
        assert p.open_access_url == "https://example.com/paper/1.pdf"
        assert p.abstract == "Digital transformation drives tourism growth."
        assert p.language == "en"
        assert p.source == "openalex"


def test_search_caching() -> None:
    """Kiểm tra cơ chế cache: lần gọi thứ hai cùng tham số không gọi ra mạng."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [_create_mock_work_item()]
    }

    with patch("requests.get", return_value=mock_response) as mock_get:
        # Lần 1: Gọi API và ghi cache
        papers_1 = search(query="cached query", year_from=2021, limit=5, page=1)
        assert len(papers_1) == 1
        assert mock_get.call_count == 1

        # Lần 2: Đọc từ cache, không gọi lại requests.get
        papers_2 = search(query="cached query", year_from=2021, limit=5, page=1)
        assert len(papers_2) == 1
        assert mock_get.call_count == 1  # Không tăng thêm
        assert papers_1[0].title == papers_2[0].title
        assert papers_1[0].doi == papers_2[0].doi


def test_search_retry_on_429_and_500() -> None:
    """Kiểm tra tự động thử lại tối đa 2 lần khi gặp lỗi 429 hoặc 5xx và thành công ở lần sau."""
    resp_429 = MagicMock()
    resp_429.status_code = 429

    resp_500 = MagicMock()
    resp_500.status_code = 500

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"results": [_create_mock_work_item()]}

    with patch("requests.get", side_effect=[resp_429, resp_500, resp_200]) as mock_get:
        papers = search(query="retry test", year_from=2022, limit=5, page=1)
        assert len(papers) == 1
        assert mock_get.call_count == 3


def test_search_retry_exhausted_returns_empty_list() -> None:
    """Kiểm tra khi retry hết lượt mà vẫn lỗi thì trả về danh sách rỗng, không crash app."""
    resp_503 = MagicMock()
    resp_503.status_code = 503

    with patch("requests.get", return_value=resp_503) as mock_get:
        papers = search(query="fail test", year_from=2022, limit=5, page=1)
        assert papers == []
        assert mock_get.call_count == 3


def test_search_network_exception_returns_empty_list() -> None:
    """Kiểm tra khi lỗi mạng/timeout thì thử lại rồi trả về danh sách rỗng, không crash app."""
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Timeout")) as mock_get:
        papers = search(query="timeout test", year_from=2022, limit=5, page=1)
        assert papers == []
        assert mock_get.call_count == 3


def test_search_empty_query() -> None:
    """Kiểm tra query rỗng lập tức trả về danh sách rỗng mà không gọi API."""
    with patch("requests.get") as mock_get:
        papers = search(query="   ", year_from=2022, limit=10, page=1)
        assert papers == []
        assert mock_get.call_count == 0
