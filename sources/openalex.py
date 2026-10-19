"""
Gọi API OpenAlex để tìm kiếm tài liệu nghiên cứu kinh tế và trả về danh sách đối tượng Paper.
Đầu vào: Từ khóa truy vấn, năm bắt đầu, giới hạn số lượng bài và số trang.
Đầu ra: Danh sách các đối tượng Paper đã được chuẩn hóa và lưu cache.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Đảm bảo thư mục gốc dự án luôn có trong sys.path khi chạy trực tiếp file
_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

import requests
from dotenv import load_dotenv

from config import settings
from models.paper import Paper
from utils.file_cache import cache_get, cache_set, make_key

load_dotenv()


def normalize_doi(doi: Optional[str]) -> str:
    """
    Chuẩn hóa chuỗi DOI về định dạng tiêu chuẩn (bỏ tiền tố url/doi: và viết thường).

    Đầu vào:
        doi: Chuỗi DOI thô từ API hoặc người dùng.

    Đầu ra:
        Chuỗi DOI đã chuẩn hóa hoặc chuỗi rỗng.
    """
    if not doi:
        return ""
    doi_clean = str(doi).strip()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if doi_clean.lower().startswith(prefix):
            doi_clean = doi_clean[len(prefix):]
    return doi_clean.strip().lower()


# Gắn staticmethod normalize_doi vào Paper nếu chưa có
if not hasattr(Paper, "normalize_doi"):
    Paper.normalize_doi = staticmethod(normalize_doi)

# Hỗ trợ các thuộc tính mở rộng cho Paper
if not hasattr(Paper, "id"):
    Paper.id = property(
        lambda self: getattr(self, "_id", "") or self.doi or "",
        lambda self, v: setattr(self, "_id", v),
    )
if not hasattr(Paper, "venue"):
    Paper.venue = property(
        lambda self: getattr(self, "_venue", None) or self.journal,
        lambda self, v: (setattr(self, "_venue", v), setattr(self, "journal", v)),
    )
if not hasattr(Paper, "citation_count"):
    Paper.citation_count = property(
        lambda self: getattr(self, "_citation_count", None) or self.citations,
        lambda self, v: (setattr(self, "_citation_count", v), setattr(self, "citations", v)),
    )
if not hasattr(Paper, "is_open_access"):
    Paper.is_open_access = property(
        lambda self: getattr(self, "_is_open_access", False),
        lambda self, v: setattr(self, "_is_open_access", v),
    )
if not hasattr(Paper, "open_access_url"):
    Paper.open_access_url = property(
        lambda self: getattr(self, "_open_access_url", ""),
        lambda self, v: setattr(self, "_open_access_url", v),
    )
if not hasattr(Paper, "language"):
    Paper.language = property(
        lambda self: getattr(self, "_language", ""),
        lambda self, v: setattr(self, "_language", v),
    )


def reconstruct_abstract(inverted_index: Optional[dict[str, list[int]]]) -> str:
    """
    Dựng lại đoạn văn bản abstract hoàn chỉnh từ abstract_inverted_index của OpenAlex.

    Đầu vào:
        inverted_index: Dict ánh xạ từ/dấu câu sang danh sách vị trí xuất hiện.

    Đầu ra:
        Chuỗi văn bản abstract hoàn chỉnh theo đúng thứ tự từ ngữ.
    """
    if not inverted_index or not isinstance(inverted_index, dict):
        return ""

    word_positions: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        if isinstance(positions, list):
            for pos in positions:
                if isinstance(pos, int):
                    word_positions.append((pos, str(word)))

    if not word_positions:
        return ""

    word_positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in word_positions)


def _paper_to_cache_dict(paper: Paper) -> dict[str, Any]:
    """Chuyển đổi Paper sang dictionary đầy đủ để lưu cache."""
    data = paper.to_dict()
    data["id"] = getattr(paper, "id", "")
    data["venue"] = getattr(paper, "venue", paper.journal)
    data["citation_count"] = getattr(paper, "citation_count", paper.citations)
    data["is_open_access"] = getattr(paper, "is_open_access", False)
    data["open_access_url"] = getattr(paper, "open_access_url", "")
    data["language"] = getattr(paper, "language", "")
    return data


def _dict_to_paper(data: dict[str, Any]) -> Paper:
    """Khôi phục đối tượng Paper từ dictionary cache."""
    paper = Paper.from_dict(data)
    if "id" in data:
        paper.id = str(data["id"])
    if "venue" in data:
        paper.venue = str(data["venue"])
    if "citation_count" in data:
        try:
            paper.citation_count = int(data["citation_count"])
        except (ValueError, TypeError):
            pass
    if "is_open_access" in data:
        paper.is_open_access = bool(data["is_open_access"])
    if "open_access_url" in data:
        paper.open_access_url = str(data["open_access_url"])
    if "language" in data:
        paper.language = str(data["language"])
    return paper


def search(query: str, year_from: int, limit: int, page: int = 1) -> list[Paper]:
    """
    Tìm kiếm bài báo học thuật qua OpenAlex API có hỗ trợ cache và cơ chế retry khi lỗi.

    Đầu vào:
        query: Từ khóa tìm kiếm.
        year_from: Năm xuất bản bắt đầu lấy dữ liệu.
        limit: Số lượng bài báo tối đa trong một trang.
        page: Số thứ tự trang kết quả (mặc định là 1).

    Đầu ra:
        Danh sách các đối tượng Paper thu thập được (hoặc rỗng nếu lỗi).
    """
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    cache_key = make_key(cleaned_query.lower(), str(year_from), str(limit), str(page))
    ttl_seconds = int(getattr(settings, "HTTP_CACHE_TTL_HOURS", 24)) * 3600

    cached_data = cache_get("openalex", cache_key, ttl_seconds=ttl_seconds)
    if cached_data is not None and isinstance(cached_data, list):
        return [_dict_to_paper(item) for item in cached_data]

    url = "https://api.openalex.org/works"
    params: dict[str, Any] = {
        "search": cleaned_query,
        "per-page": limit,
        "page": page,
        "filter": f"from_publication_date:{year_from}-01-01,has_abstract:true",
        "select": "id,doi,title,authorships,publication_year,primary_location,cited_by_count,open_access,abstract_inverted_index,language",
    }

    email = os.getenv("OPENALEX_EMAIL", "").strip()
    if email:
        params["mailto"] = email

    headers = {"User-Agent": "ResearchFinder/1.0"}

    max_retries = 2
    backoff_factor = 1.0
    response_data: Optional[dict[str, Any]] = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                response_data = response.json()
                break
            elif response.status_code in (429, 500, 502, 503, 504):
                if attempt < max_retries:
                    time.sleep(backoff_factor * (2**attempt))
                    continue
                return []
            else:
                return []
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            if attempt < max_retries:
                time.sleep(backoff_factor * (2**attempt))
                continue
            return []
        except Exception:
            return []

    if not response_data or "results" not in response_data:
        return []

    papers: list[Paper] = []
    for item in response_data.get("results", []):
        raw_doi = item.get("doi")
        normalized_doi_str = Paper.normalize_doi(raw_doi)

        primary_location = item.get("primary_location") or {}
        source_obj = primary_location.get("source") or {}
        venue = source_obj.get("display_name", "") or ""

        landing_url = primary_location.get("landing_page_url") or item.get("doi") or item.get("id") or ""

        authorships = item.get("authorships") or []
        authors: list[str] = []
        for a in authorships:
            author_dict = a.get("author") or {}
            name = author_dict.get("display_name")
            if name:
                authors.append(str(name))

        year = item.get("publication_year")
        citation_count = item.get("cited_by_count", 0) or 0

        oa_info = item.get("open_access") or {}
        is_oa = bool(oa_info.get("is_oa", False))
        oa_url = str(oa_info.get("oa_url", "") or "")

        abstract_text = reconstruct_abstract(item.get("abstract_inverted_index"))
        language = str(item.get("language", "") or "")

        paper = Paper(
            title=str(item.get("title", "") or ""),
            authors=authors,
            year=int(year) if year is not None else None,
            journal=venue,
            doi=normalized_doi_str,
            url=str(landing_url),
            citations=int(citation_count),
            abstract=abstract_text,
            source="openalex",
        )

        paper.id = normalized_doi_str if normalized_doi_str else str(item.get("id", "") or "")
        paper.venue = venue
        paper.citation_count = int(citation_count)
        paper.is_open_access = is_oa
        paper.open_access_url = oa_url
        paper.language = language

        papers.append(paper)

    cache_set("openalex", cache_key, [_paper_to_cache_dict(p) for p in papers])
    return papers


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    test_query = "digital ecosystem tourism export"
    print(f"Bắt đầu tìm kiếm thử nghiệm OpenAlex với từ khóa: '{test_query}'...")
    results = search(test_query, year_from=2020, limit=10, page=1)
    print(f"\nTìm thấy {len(results)} bài báo:")
    for idx, paper in enumerate(results, 1):
        print(f"{idx}. {paper.title} ({paper.year})")
        print(f"   Tác giả: {', '.join(paper.authors[:3])}")
        print(f"   DOI: {paper.doi} | Trích dẫn: {paper.citations}")
        print(f"   Tạp chí: {paper.journal} | Open Access: {paper.is_open_access}")
        print()
