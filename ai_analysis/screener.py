"""
Sàng lọc nhanh và chấm điểm sơ bộ mức độ liên quan của các bài báo với đề tài nghiên cứu.
Đầu vào: Danh sách đối tượng Paper và đề tài nghiên cứu kinh tế.
Đầu ra: Cùng danh sách Paper đã được gán relevance_score (0-100 hoặc None nếu lỗi).
"""

from __future__ import annotations

import logging
from typing import Any

from ai_analysis.llm_client import call_llm_json
from config import settings
from models.paper import Paper

logger = logging.getLogger(__name__)


def score_papers(papers: list[Paper], topic: str) -> list[Paper]:
    """
    Chấm điểm sơ bộ mức độ liên quan (0-100) của các bài báo với đề tài nghiên cứu kinh tế.
    Gộp theo lô tối đa CANDIDATE_POOL_SIZE bài trong một lần gọi call_llm_json để tiết kiệm token.

    Đầu vào:
        papers: Danh sách các đối tượng Paper cần chấm điểm.
        topic: Đề tài hoặc câu hỏi nghiên cứu của người dùng.

    Đầu ra:
        Danh sách các đối tượng Paper đã được cập nhật relevance_score.
    """
    if not papers:
        return []

    clean_topic = topic.strip()
    if not clean_topic:
        for p in papers:
            p.relevance_score = None
        return papers

    batch_size = int(getattr(settings, "CANDIDATE_POOL_SIZE", 30))
    abstract_chars_limit = int(getattr(settings, "SCREEN_ABSTRACT_CHARS", 500))
    no_abstract_cap = int(getattr(settings, "NO_ABSTRACT_SCORE_CAP", 60))

    # Chia danh sách thành các lô có kích thước tối đa CANDIDATE_POOL_SIZE
    for start_idx in range(0, len(papers), batch_size):
        batch = papers[start_idx : start_idx + batch_size]

        # Chuẩn bị nội dung prompt cho từng bài: chỉ gồm i, tiêu đề, năm, abstract rút gọn
        lines: list[str] = [
            f"Chỉ dùng thông tin trong văn bản được cung cấp. Không bịa. Chấm mức phù hợp với đề tài nghiên cứu: {clean_topic}.\n",
            "Danh sách bài báo:",
        ]

        for i, paper in enumerate(batch, 1):
            title = paper.title or "Không có tiêu đề"
            year_val = str(paper.year) if paper.year is not None else "N/A"
            abstract_text = (paper.abstract or "").strip()[:abstract_chars_limit]
            if not abstract_text:
                abstract_text = "(Không có tóm tắt)"

            lines.append(f"[{i}] Tiêu đề: {title}\nNăm: {year_val}\nAbstract: {abstract_text}\n")

        lines.append(
            'Yêu cầu: Đánh giá độ phù hợp của từng bài theo thang điểm 0-100. '
            'Chỉ trả về JSON thuần túy theo định dạng: {"scores": [{"i": 1, "s": 85}, ...]}'
        )

        prompt = "\n".join(lines)
        system_prompt = (
            "You are a rigorous economic research evaluator. "
            "Score each paper's relevance to the topic from 0 to 100 based strictly on provided text. "
            "Output valid JSON only."
        )

        max_tokens = max(512, len(batch) * 35)

        try:
            response_data = call_llm_json(
                prompt=prompt,
                system=system_prompt,
                max_output_tokens=max_tokens,
                use_cache=True,
            )

            # Phân tích danh sách điểm số từ phản hồi
            score_map: dict[int, int] = {}
            raw_scores: list[dict[str, Any]] = []

            if isinstance(response_data, dict):
                raw_scores = response_data.get("scores", [])
            elif isinstance(response_data, list):
                raw_scores = response_data

            if isinstance(raw_scores, list):
                for item in raw_scores:
                    if isinstance(item, dict) and "i" in item and "s" in item:
                        try:
                            item_i = int(item["i"])
                            item_s = int(item["s"])
                            score_map[item_i] = item_s
                        except (ValueError, TypeError):
                            continue

            # Ghép điểm theo i (không phụ thuộc thứ tự trả về của AI)
            for i, paper in enumerate(batch, 1):
                if i in score_map:
                    raw_s = score_map[i]
                    # Cắt về khoảng hợp lệ 0-100
                    clamped_s = max(0, min(100, raw_s))

                    # Chặn trần NO_ABSTRACT_SCORE_CAP nếu bài không có abstract
                    if not (paper.abstract or "").strip():
                        clamped_s = min(clamped_s, no_abstract_cap)

                    paper.relevance_score = clamped_s
                else:
                    # Bài AI bỏ sót: gán điểm 0 và ghi log cảnh báo
                    logger.warning(
                        "Bài số %d ('%s') bị AI bỏ sót điểm chấm, gán 0.",
                        i,
                        paper.title,
                    )
                    paper.relevance_score = 0

        except Exception as exc:
            # Lỗi gọi LLM: ghi log và để relevance_score = None, không ném lỗi
            logger.error("Lỗi khi chấm điểm batch bài báo qua LLM: %s", exc)
            for paper in batch:
                paper.relevance_score = None

    return papers
