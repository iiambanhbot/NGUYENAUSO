"""
Gộp kết quả từ các nguồn khác nhau, loại bỏ bài trùng lặp và xếp hạng danh sách bài báo.
Đầu vào: Danh sách các danh sách Paper thu thập từ nhiều nguồn, tập các khóa cần loại trừ.
Đầu ra: Danh sách bài báo duy nhất đã được loại trùng, gộp dữ liệu đầy đủ và xếp hạng.
"""

from __future__ import annotations

import copy
from typing import Optional

from models.paper import Paper


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


if not hasattr(Paper, "normalize_doi"):
    Paper.normalize_doi = staticmethod(normalize_doi)


def get_dedupe_key(paper: Paper) -> str:
    """
    Tạo khóa định danh duy nhất để khử trùng bài báo.
    Ưu tiên sử dụng DOI chuẩn hóa; nếu không có DOI thì dùng tiêu đề chuẩn hóa kết hợp năm xuất bản.

    Đầu vào:
        paper: Đối tượng Paper cần lấy khóa.

    Đầu ra:
        Chuỗi khóa định danh dạng 'doi:<doi>' hoặc 'title_year:<slug>_<year>'.
    """
    raw_doi = getattr(paper, "doi", None)
    if raw_doi:
        normalized_doi = normalize_doi(raw_doi)
        if normalized_doi:
            return f"doi:{normalized_doi}"

    title = (getattr(paper, "title", "") or "").strip().lower()
    title_clean = "".join(c for c in title if c.isalnum() or c.isspace())
    title_slug = "_".join(title_clean.split())
    year = str(getattr(paper, "year", "") or "")
    return f"title_year:{title_slug}_{year}"


# Gắn property dedupe_key vào Paper nếu chưa có
if not hasattr(Paper, "dedupe_key"):
    Paper.dedupe_key = property(get_dedupe_key)


def _completeness_score(paper: Paper) -> int:
    """Tính điểm độ đầy đủ dữ liệu của một bài báo để ưu tiên giữ làm bản gốc."""
    score = 0
    if getattr(paper, "doi", None):
        score += 100
    abstract = getattr(paper, "abstract", "") or ""
    if abstract:
        score += len(abstract)
    if getattr(paper, "authors", None):
        score += len(paper.authors) * 10
    if getattr(paper, "journal", "") or getattr(paper, "venue", ""):
        score += 20
    if getattr(paper, "citations", 0) or getattr(paper, "citation_count", 0):
        score += 10
    if getattr(paper, "url", ""):
        score += 10
    return score


def _combine_papers(paper_a: Paper, paper_b: Paper) -> Paper:
    """
    Kết hợp hai bài báo trùng lặp: chọn bản đầy đủ hơn làm gốc và bổ sung các trường còn thiếu từ bản kia.
    """
    score_a = _completeness_score(paper_a)
    score_b = _completeness_score(paper_b)

    base = copy.deepcopy(paper_a if score_a >= score_b else paper_b)
    other = paper_b if score_a >= score_b else paper_a

    # Bổ sung các trường còn thiếu
    if not base.title and other.title:
        base.title = other.title

    if not base.doi and other.doi:
        base.doi = normalize_doi(other.doi)

    if not base.authors and other.authors:
        base.authors = copy.deepcopy(other.authors)

    if base.year is None and other.year is not None:
        base.year = other.year

    venue_other = getattr(other, "venue", other.journal)
    if not getattr(base, "journal", "") and venue_other:
        base.journal = venue_other
        setattr(base, "venue", venue_other)

    if not base.url and other.url:
        base.url = other.url

    citations_base = getattr(base, "citation_count", base.citations)
    citations_other = getattr(other, "citation_count", other.citations)
    max_citations = max(citations_base or 0, citations_other or 0)
    base.citations = max_citations
    setattr(base, "citation_count", max_citations)

    if not base.abstract and other.abstract:
        base.abstract = other.abstract

    is_oa = getattr(base, "is_open_access", False) or getattr(other, "is_open_access", False)
    setattr(base, "is_open_access", is_oa)

    other_oa_url = getattr(other, "open_access_url", "")
    if other_oa_url and not getattr(base, "open_access_url", ""):
        setattr(base, "open_access_url", other_oa_url)

    other_lang = getattr(other, "language", "")
    if other_lang and not getattr(base, "language", ""):
        setattr(base, "language", other_lang)

    # Các trường AI và ghi chú
    if not base.relevance_score and other.relevance_score:
        base.relevance_score = other.relevance_score
    if not base.relevance_reason and other.relevance_reason:
        base.relevance_reason = other.relevance_reason
    if not base.summary and other.summary:
        base.summary = other.summary
    if not base.methodology and other.methodology:
        base.methodology = other.methodology
    if not base.data_source and other.data_source:
        base.data_source = other.data_source
    if not base.key_findings and other.key_findings:
        base.key_findings = other.key_findings
    if not getattr(base, "limitations", "") and getattr(other, "limitations", ""):
        base.limitations = other.limitations
    if not base.policy_implications and other.policy_implications:
        base.policy_implications = other.policy_implications
    if not base.notes and other.notes:
        base.notes = other.notes
    base.analyzed = base.analyzed or other.analyzed

    return base


def merge(lists: list[list[Paper]], exclude_keys: set[str]) -> list[Paper]:
    """
    Gộp các danh sách bài báo, loại trùng theo Paper.dedupe_key và loại bỏ các bài thuộc exclude_keys.
    Khi phát hiện trùng, giữ bản đầy đủ hơn (có abstract, có DOI) và bổ sung các trường còn thiếu từ bản kia.

    Đầu vào:
        lists: Danh sách các danh sách bài báo từ các nguồn khác nhau.
        exclude_keys: Tập hợp các khóa định danh cần loại trừ (ví dụ bài đã hiển thị/đã lưu).

    Đầu ra:
        Danh sách các đối tượng Paper duy nhất đã được chuẩn hóa và bổ sung dữ liệu.
    """
    merged_dict: dict[str, Paper] = {}
    ordered_keys: list[str] = []

    for paper_list in lists:
        if not paper_list:
            continue
        for paper in paper_list:
            if not isinstance(paper, Paper):
                continue

            key = paper.dedupe_key if hasattr(paper, "dedupe_key") else get_dedupe_key(paper)
            if not key or key in exclude_keys:
                continue

            if key not in merged_dict:
                merged_dict[key] = copy.deepcopy(paper)
                ordered_keys.append(key)
            else:
                existing_paper = merged_dict[key]
                merged_dict[key] = _combine_papers(existing_paper, paper)

    return [merged_dict[k] for k in ordered_keys]


def rank(papers: list[Paper]) -> list[Paper]:
    """
    Sắp xếp danh sách bài báo:
    - Các bài đã có relevance_score (> 0) xếp trước theo relevance_score giảm dần.
    - Các bài chưa có điểm (hoặc điểm = 0) xếp sau, sắp xếp theo citation_count / citations giảm dần.

    Đầu vào:
        papers: Danh sách các bài báo cần sắp xếp.

    Đầu ra:
        Danh sách bài báo đã được sắp xếp theo thứ tự ưu tiên.
    """
    if not papers:
        return []

    def sort_key(p: Paper) -> tuple[int, int, int, int]:
        score = p.relevance_score or 0
        has_score = 1 if score > 0 else 0
        cit = getattr(p, "citation_count", p.citations) or 0
        year = p.year or 0
        return (-has_score, -score, -cit, -year)

    return sorted(papers, key=sort_key)
