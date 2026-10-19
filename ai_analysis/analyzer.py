"""
Phân tích chuyên sâu bài báo: tóm tắt ngắn, tóm tắt chi tiết và trích xuất dữ liệu nghiên cứu chỉ dựa trên abstract.
Đầu vào: Danh sách đối tượng Paper và đề tài nghiên cứu.
Đầu ra: Cùng danh sách Paper đã được điền short_summary, detail_summary, extracted_data và analyzed=True/False.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from ai_analysis.llm_client import call_llm_json
from config import settings
from merge.dedupe_rank import get_dedupe_key
from models.paper import Paper
from utils.file_cache import cache_get, cache_set, make_key

logger = logging.getLogger(__name__)


class ExtractedData:
    """Đối tượng lưu trữ các trường dữ liệu nghiên cứu được trích xuất từ abstract."""

    def __init__(
        self,
        basis: str = "",
        method: Optional[str] = None,
        sample: Optional[str] = None,
        variables: Optional[list[str]] = None,
        countries: Optional[list[str]] = None,
        main_findings: Optional[str] = None,
        limitations: Optional[str] = None,
    ) -> None:
        self.basis = basis
        self.method = method
        self.sample = sample
        self.variables = variables if variables is not None else []
        self.countries = countries if countries is not None else []
        self.main_findings = main_findings
        self.limitations = limitations

    def to_dict(self) -> dict[str, Any]:
        """Chuyển đổi sang dict phục vụ lưu cache JSON."""
        return {
            "basis": self.basis,
            "method": self.method,
            "sample": self.sample,
            "variables": self.variables,
            "countries": self.countries,
            "main_findings": self.main_findings,
            "limitations": self.limitations,
        }

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


def _get_paper_key(paper: Paper) -> str:
    """Lấy khóa định danh của bài báo để tạo cache key."""
    if hasattr(paper, "dedupe_key"):
        return str(paper.dedupe_key)
    return get_dedupe_key(paper)


def _apply_analysis_to_paper(paper: Paper, data: dict[str, Any]) -> None:
    """Gán dữ liệu phân tích chi tiết vào đối tượng Paper."""
    short_summary = str(data.get("short_summary", "") or "").strip()
    detail_summary = str(data.get("detail_summary", "") or "").strip()

    raw_method = data.get("method")
    method = str(raw_method).strip() if raw_method is not None else None

    raw_sample = data.get("sample")
    sample = str(raw_sample).strip() if raw_sample is not None else None

    raw_findings = data.get("main_findings")
    main_findings = str(raw_findings).strip() if raw_findings is not None else None

    raw_limitations = data.get("limitations")
    limitations = str(raw_limitations).strip() if raw_limitations is not None else None

    raw_vars = data.get("variables")
    variables: list[str] = (
        [str(v).strip() for v in raw_vars if str(v).strip()]
        if isinstance(raw_vars, list)
        else []
    )

    raw_countries = data.get("countries")
    countries: list[str] = (
        [str(c).strip() for c in raw_countries if str(c).strip()]
        if isinstance(raw_countries, list)
        else []
    )

    extracted = ExtractedData(
        basis=str(data.get("basis", "abstract")),
        method=method,
        sample=sample,
        variables=variables,
        countries=countries,
        main_findings=main_findings,
        limitations=limitations,
    )

    setattr(paper, "short_summary", short_summary)
    paper.summary = short_summary
    setattr(paper, "detail_summary", detail_summary)
    setattr(paper, "extracted_data", extracted)

    if method:
        paper.methodology = method
    if sample:
        paper.data_source = sample
    if main_findings:
        paper.key_findings = main_findings
    if limitations:
        paper.limitations = limitations
    setattr(paper, "limitations", paper.limitations)
    if variables:
        setattr(paper, "variables", ", ".join(variables))
    if countries:
        setattr(paper, "country", ", ".join(countries))

    paper.analyzed = True


def _build_analysis_prompt(papers_with_index: list[tuple[int, Paper]], topic: str) -> str:
    """Xây dựng prompt yêu cầu phân tích theo đúng cấu trúc JSON."""
    char_limit = int(getattr(settings, "ANALYZE_ABSTRACT_CHARS", 1800))
    lines: list[str] = [
        "Chỉ dùng thông tin có trong abstract. Thông tin không có thì để null hoặc []. Tuyệt đối không suy đoán hay bịa.",
        f"Đề tài nghiên cứu: {topic}\n",
        "Danh sách bài báo:",
    ]

    for i, paper in papers_with_index:
        title = paper.title or "Không có tiêu đề"
        year_str = str(paper.year) if paper.year is not None else "N/A"
        abstract = (paper.abstract or "").strip()[:char_limit]
        lines.append(f"[{i}] Tiêu đề: {title}\nNăm: {year_str}\nAbstract: {abstract}\n")

    lines.append(
        "Yêu cầu: Trả về một mảng JSON các đối tượng, mỗi phần tử gồm:\n"
        '- "i": số thứ tự tương ứng (số nguyên)\n'
        '- "short_summary": tiếng Việt, tối đa 2 câu (khoảng 40 từ)\n'
        f'- "detail_summary": tiếng Việt, tối đa 120 từ, nêu bài này liên quan gì đến đề tài "{topic}"\n'
        '- "method": chuỗi ngắn nêu phương pháp hoặc null\n'
        '- "sample": chuỗi ngắn nêu mẫu/dữ liệu hoặc null\n'
        '- "variables": danh sách ngắn các biến số hoặc []\n'
        '- "countries": danh sách ngắn các quốc gia nghiên cứu hoặc []\n'
        '- "main_findings": chuỗi ngắn nêu kết quả chính hoặc null\n'
        f'- "limitations": tiếng Việt, 1-2 câu nêu rõ hạn chế của thông tin bài báo đối với đề tài nghiên cứu "{topic}" (bài báo còn thiếu thông tin gì, chưa đề cập/không nêu được khía cạnh nào so với đề tài)'
    )
    return "\n".join(lines)


def _call_and_parse_batch(
    papers_with_index: list[tuple[int, Paper]],
    topic: str,
) -> dict[int, dict[str, Any]]:
    """Gọi LLM và ánh xạ kết quả trả về theo số thứ tự i."""
    prompt = _build_analysis_prompt(papers_with_index, topic)
    system_prompt = (
        "You are a rigorous economic research analyst. "
        "Strictly analyze papers based solely on their abstracts. "
        "Output valid JSON array only."
    )
    max_tokens = min(8192, max(2048, len(papers_with_index) * 600))

    response_data = call_llm_json(
        prompt=prompt,
        system=system_prompt,
        max_output_tokens=max_tokens,
        use_cache=True,
    )

    items: list[dict[str, Any]] = []
    if isinstance(response_data, list):
        items = response_data
    elif isinstance(response_data, dict):
        if "papers" in response_data and isinstance(response_data["papers"], list):
            items = response_data["papers"]
        elif "results" in response_data and isinstance(response_data["results"], list):
            items = response_data["results"]
        else:
            items = [response_data]

    result_map: dict[int, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and "i" in item:
            try:
                item_i = int(item["i"])
                result_map[item_i] = item
            except (ValueError, TypeError):
                continue
    return result_map


def analyze_papers(papers: list[Paper], topic: str) -> list[Paper]:
    """
    Phân tích chuyên sâu danh sách bài báo: tóm tắt sơ lược, tóm tắt chi tiết và trích xuất dữ liệu.
    - Bài không có abstract: không gửi cho AI, đặt short_summary='Không có abstract để tóm tắt', basis='none', analyzed=True.
    - Bài có abstract: kiểm tra cache từng bài (namespace 'analysis').
    - Các bài chưa có cache: gộp theo lô tối đa 10 bài/lần gọi.
    - Ghép kết quả theo i. Bài AI bỏ sót: thử lại đúng 1 lần chỉ với bài đó; vẫn lỗi thì để analyzed=False.
    - Lỗi mạng/AI: không ném ngoại lệ, đặt analyzed=False.

    Đầu vào:
        papers: Danh sách các đối tượng Paper.
        topic: Đề tài nghiên cứu của người dùng.

    Đầu ra:
        Cùng danh sách Paper đã cập nhật phân tích.
    """
    if not papers:
        return []

    clean_topic = topic.strip()
    model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    ttl_days = int(getattr(settings, "AI_CACHE_TTL_DAYS", 30))
    ttl_seconds = ttl_days * 86400

    papers_to_analyze: list[Paper] = []

    # 1. Phân loại bài: không có abstract vs có abstract (kiểm tra cache từng bài)
    for paper in papers:
        abstract = (paper.abstract or "").strip()
        if not abstract:
            # Bài không có abstract: không gửi AI
            no_abs_text = "Không có abstract để tóm tắt"
            setattr(paper, "short_summary", no_abs_text)
            paper.summary = no_abs_text
            setattr(paper, "detail_summary", no_abs_text)
            setattr(paper, "extracted_data", ExtractedData(basis="none"))
            paper.analyzed = True
            continue

        # Kiểm tra cache riêng từng bài
        cache_key = make_key(_get_paper_key(paper), clean_topic, model)
        cached_data = cache_get("analysis", cache_key, ttl_seconds=ttl_seconds)

        if cached_data is not None and isinstance(cached_data, dict):
            if "limitations" in cached_data:
                _apply_analysis_to_paper(paper, cached_data)
            else:
                setattr(paper, "_old_cached_data", cached_data)
                papers_to_analyze.append(paper)
        else:
            papers_to_analyze.append(paper)

    if not papers_to_analyze or not clean_topic:
        return papers

    # 2. Xử lý các bài chưa có cache theo lô tối đa 10 bài/lần gọi
    batch_size = 10
    for start_idx in range(0, len(papers_to_analyze), batch_size):
        batch = papers_to_analyze[start_idx : start_idx + batch_size]
        indexed_batch = list(enumerate(batch, 1))

        try:
            result_map = _call_and_parse_batch(indexed_batch, clean_topic)
        except Exception as exc:
            logger.error("Lỗi khi phân tích batch bài báo: %s", exc)
            for paper in batch:
                old_cache = getattr(paper, "_old_cached_data", None)
                if old_cache:
                    _apply_analysis_to_paper(paper, old_cache)
                else:
                    paper.analyzed = False
            continue

        # Kiểm tra bài nào thành công và bài nào bị AI bỏ sót / trả hỏng
        missing_entries: list[tuple[int, Paper]] = []
        for i, paper in indexed_batch:
            if i in result_map:
                data = result_map[i]
                data["basis"] = "abstract"
                _apply_analysis_to_paper(paper, data)

                # Lưu cache cho từng bài thành công
                cache_key = make_key(_get_paper_key(paper), clean_topic, model)
                cache_payload = {
                    "short_summary": paper.summary,
                    "detail_summary": getattr(paper, "detail_summary", ""),
                    "basis": "abstract",
                    "method": getattr(paper, "methodology", None),
                    "sample": getattr(paper, "data_source", None),
                    "variables": (
                        [v.strip() for v in getattr(paper, "variables", "").split(",") if v.strip()]
                        if getattr(paper, "variables", "")
                        else []
                    ),
                    "countries": (
                        [c.strip() for c in getattr(paper, "country", "").split(",") if c.strip()]
                        if getattr(paper, "country", "")
                        else []
                    ),
                    "main_findings": getattr(paper, "key_findings", None),
                    "limitations": getattr(paper, "limitations", None),
                }
                cache_set("analysis", cache_key, cache_payload)
            else:
                missing_entries.append((i, paper))

        # 3. Thử lại đúng 1 lần cho những bài bị bỏ sót
        if missing_entries:
            retry_indexed = [(idx, p) for idx, (_, p) in enumerate(missing_entries, 1)]
            try:
                retry_map = _call_and_parse_batch(retry_indexed, clean_topic)
                for retry_i, (_, paper) in enumerate(missing_entries, 1):
                    if retry_i in retry_map:
                        data = retry_map[retry_i]
                        data["basis"] = "abstract"
                        _apply_analysis_to_paper(paper, data)

                        cache_key = make_key(_get_paper_key(paper), clean_topic, model)
                        cache_payload = {
                            "short_summary": paper.summary,
                            "detail_summary": getattr(paper, "detail_summary", ""),
                            "basis": "abstract",
                            "method": getattr(paper, "methodology", None),
                            "sample": getattr(paper, "data_source", None),
                            "variables": (
                                [v.strip() for v in getattr(paper, "variables", "").split(",") if v.strip()]
                                if getattr(paper, "variables", "")
                                else []
                            ),
                            "countries": (
                                [c.strip() for c in getattr(paper, "country", "").split(",") if c.strip()]
                                if getattr(paper, "country", "")
                                else []
                            ),
                            "main_findings": getattr(paper, "key_findings", None),
                            "limitations": getattr(paper, "limitations", None),
                        }
                        cache_set("analysis", cache_key, cache_payload)
                    else:
                        paper.analyzed = False
            except Exception as exc:
                logger.error("Lỗi khi thử lại cho các bài bị bỏ sót: %s", exc)
                for _, paper in missing_entries:
                    paper.analyzed = False

    return papers
