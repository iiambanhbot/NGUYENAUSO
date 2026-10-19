"""
Điều phối luồng tìm kiếm, lọc trùng, sàng lọc và phân tích tài liệu nghiên cứu kinh tế.
Đầu vào: Chủ đề nghiên cứu, SelectionStore và năm xuất bản bắt đầu.
Đầu ra: Danh sách các bài báo nghiên cứu đã được xử lý hoàn chỉnh theo lô.
"""

from __future__ import annotations

import logging
from typing import Any

from ai_analysis.analyzer import analyze_papers
from ai_analysis.screener import score_papers
from config import settings
from merge.dedupe_rank import merge, rank
from models.paper import Paper
from query.keyword_builder import build_keywords
from selection.state import SelectionStore
from sources import openalex

logger = logging.getLogger(__name__)


def run_first_search(
    topic: str,
    store: SelectionStore,
    year_from: int,
    on_progress: Any | None = None,
    batch_size: int | None = None,
) -> list[Paper]:
    """
    Khởi chạy lượt tìm kiếm đầu tiên cho một đề tài nghiên cứu mới:
    1. Reset store, đặt topic, sinh từ khóa song ngữ qua build_keywords (AI call 1) và lưu vào store.keywords.
    2. Thu thập ứng viên từ OpenAlex: primary_en (limit ~20-40) và vi[0] nếu có (limit ~10-16).
       Nếu USE_SEMANTIC_SCHOLAR bật thì gọi thêm Semantic Scholar. Ghi lại store.offsets.
    3. merge → score_papers (AI call 2) → rank → nạp toàn bộ vào store.pool.
    4. batch = store.take_from_pool(batch_size or FIRST_BATCH_SIZE) → analyze_papers(batch, topic) (AI call 3)
       → store.add_papers(batch) → trả về batch.

    Đầu vào:
        topic: Chủ đề hoặc câu hỏi nghiên cứu người dùng nhập.
        store: Đối tượng SelectionStore quản lý trạng thái phiên.
        year_from: Năm xuất bản bắt đầu lấy tài liệu.
        on_progress: Callback tùy chọn nhận (progress_float, message_str) để cập nhật thanh tiến trình.
        batch_size: Số lượng bài báo cần hiển thị đợt đầu (tùy chọn: 5, 10, 15, 20... mặc định FIRST_BATCH_SIZE).

    Đầu ra:
        Danh sách bài báo đợt đầu (tối đa batch_size bài) đã phân tích để hiển thị.
    """
    def _report(pct: float, msg: str) -> None:
        if on_progress and callable(on_progress):
            try:
                on_progress(pct, msg)
            except Exception:
                pass

    clean_topic = topic.strip()
    if not clean_topic:
        store.reset()
        return []

    first_batch_size = int(batch_size) if batch_size is not None else int(getattr(settings, "FIRST_BATCH_SIZE", 10))

    # 1. Reset và sinh từ khóa song ngữ (1 lần gọi AI)
    _report(0.12, "Phân tích đề tài & xây dựng từ khóa học thuật...")
    store.reset()
    store.topic = clean_topic
    store.target_count = first_batch_size

    try:
        keywords = build_keywords(clean_topic)
    except Exception as exc:
        logger.error("Lỗi khi sinh từ khóa: %s", exc)
        keywords = {"primary_en": clean_topic, "en": [], "vi": [clean_topic]}

    store.keywords = keywords

    # 2. Lấy ứng viên từ các nguồn học thuật
    _report(0.38, "Tìm kiếm bài báo từ các cơ sở dữ liệu học thuật...")
    primary_en = keywords.get("primary_en", "") or clean_topic
    vi_keywords = keywords.get("vi", [])
    primary_vi = vi_keywords[0] if vi_keywords and vi_keywords[0] else ""

    source_lists: list[list[Paper]] = []

    # OpenAlex tiếng Anh (tối thiểu 20 bài hoặc 2x first_batch_size để đảm bảo sàng lọc đủ bài)
    limit_en = max(20, int(first_batch_size * 2))
    openalex_en = openalex.search(primary_en, year_from=year_from, limit=limit_en, page=1)
    store.offsets["openalex_en"] = 1
    if openalex_en:
        source_lists.append(openalex_en)

    # OpenAlex tiếng Việt (nếu có từ khóa tiếng Việt)
    if primary_vi:
        limit_vi = max(10, int(first_batch_size * 0.8))
        openalex_vi = openalex.search(primary_vi, year_from=year_from, limit=limit_vi, page=1)
        store.offsets["openalex_vi"] = 1
        if openalex_vi:
            source_lists.append(openalex_vi)

    # Semantic Scholar (nếu được kích hoạt trong cấu hình)
    if getattr(settings, "USE_SEMANTIC_SCHOLAR", False):
        try:
            from sources import semantic_scholar

            if hasattr(semantic_scholar, "search"):
                ss_papers = semantic_scholar.search(primary_en, year_from=year_from, limit=limit_en)
                if ss_papers:
                    source_lists.append(ss_papers)
                    store.offsets["semantic_scholar"] = 1
        except Exception as exc:
            logger.warning("Không thể gọi Semantic Scholar: %s", exc)

    if not source_lists:
        _report(1.0, "Không tìm thấy bài báo nào từ các nguồn.")
        return []

    # 3. Gộp nguồn, khử trùng, chấm điểm sàng lọc (1 lần gọi AI), xếp hạng và lưu vào kho ứng viên
    _report(0.68, "Khử trùng lặp & chấm điểm sàng lọc bằng AI...")
    merged_candidates = merge(source_lists, exclude_keys=store.seen_keys())
    if not merged_candidates:
        _report(1.0, "Không còn bài báo mới sau khi khử trùng lặp.")
        return []

    try:
        scored_candidates = score_papers(merged_candidates, clean_topic)
    except Exception as exc:
        logger.error("Lỗi khi chấm điểm ứng viên: %s", exc)
        scored_candidates = merged_candidates

    ranked_candidates = rank(scored_candidates)
    store.add_to_pool(ranked_candidates)

    # 4. Lấy đợt đầu từ kho ứng viên và phân tích chuyên sâu (1 lần gọi AI)
    _report(0.88, "Tóm tắt & trích xuất học thuật chuyên sâu đợt đầu...")
    batch = store.take_from_pool(first_batch_size)
    if not batch:
        _report(1.0, "Đã lưu vào kho ứng viên.")
        return []

    try:
        analyzed_batch = analyze_papers(batch, clean_topic)
    except Exception as exc:
        logger.error("Lỗi khi phân tích chuyên sâu đợt đầu: %s", exc)
        analyzed_batch = batch

    store.add_papers(analyzed_batch)
    _report(1.0, f"Hoàn tất! Đã tìm thấy {len(analyzed_batch)} bài báo đầu tiên.")
    return analyzed_batch


def load_more(store: SelectionStore, year_from: int) -> list[Paper]:
    """
    Tải thêm các bài báo tiếp theo cho người dùng:
    1. Lấy LOAD_MORE_SIZE bài từ kho ứng viên store.pool.
    2. Nếu kho không đủ: tải thêm ứng viên trang kế tiếp từ các nguồn (tăng store.offsets),
       loại bài có key trong seen_keys() và pool_keys(), chấm điểm sàng lọc, thêm vào pool,
       rồi lấy tiếp phần còn thiếu.
    3. analyze_papers(batch, topic) (1 lần gọi AI nếu kho đủ) → store.add_papers → trả batch.
    Không gọi lại bước tìm kiếm mạng nếu kho ứng viên đã có đủ số bài.

    Đầu vào:
        store: Đối tượng SelectionStore.
        year_from: Năm xuất bản bắt đầu lấy tài liệu.

    Đầu ra:
        Danh sách bài báo mới được nạp thêm vào danh sách hiển thị.
    """
    topic = store.topic
    if not topic:
        return []

    load_more_size = int(getattr(settings, "LOAD_MORE_SIZE", 5))
    batch = store.take_from_pool(load_more_size)

    # Nếu kho ứng viên không đủ số lượng bài cần tải
    if len(batch) < load_more_size:
        needed = load_more_size - len(batch)
        new_source_lists: list[list[Paper]] = []

        primary_en = store.keywords.get("primary_en", "") or topic
        vi_keywords = store.keywords.get("vi", [])
        primary_vi = vi_keywords[0] if vi_keywords and vi_keywords[0] else ""

        # Tải trang tiếp theo từ OpenAlex tiếng Anh
        next_page_en = store.offsets.get("openalex_en", 1) + 1
        store.offsets["openalex_en"] = next_page_en
        more_en = openalex.search(primary_en, year_from=year_from, limit=20, page=next_page_en)
        if more_en:
            new_source_lists.append(more_en)

        # Tải trang tiếp theo từ OpenAlex tiếng Việt (nếu có)
        if primary_vi:
            next_page_vi = store.offsets.get("openalex_vi", 1) + 1
            store.offsets["openalex_vi"] = next_page_vi
            more_vi = openalex.search(primary_vi, year_from=year_from, limit=10, page=next_page_vi)
            if more_vi:
                new_source_lists.append(more_vi)

        # Semantic Scholar (nếu bật)
        if getattr(settings, "USE_SEMANTIC_SCHOLAR", False):
            try:
                from sources import semantic_scholar

                if hasattr(semantic_scholar, "search"):
                    next_page_ss = store.offsets.get("semantic_scholar", 1) + 1
                    store.offsets["semantic_scholar"] = next_page_ss
                    more_ss = semantic_scholar.search(
                        primary_en, year_from=year_from, limit=20, page=next_page_ss
                    )
                    if more_ss:
                        new_source_lists.append(more_ss)
            except Exception as exc:
                logger.warning("Lỗi load_more Semantic Scholar: %s", exc)

        # Khử trùng và loại trừ các bài đã hiển thị hoặc đã có trong pool
        exclude_keys = store.seen_keys() | store.pool_keys()
        new_merged = merge(new_source_lists, exclude_keys=exclude_keys)

        if new_merged:
            try:
                new_scored = score_papers(new_merged, topic)
            except Exception as exc:
                logger.error("Lỗi khi chấm điểm ứng viên tải thêm: %s", exc)
                new_scored = new_merged

            new_ranked = rank(new_scored)
            store.add_to_pool(new_ranked)

            # Lấy nốt phần bài còn thiếu từ pool vừa bổ sung
            additional = store.take_from_pool(needed)
            batch.extend(additional)

    if not batch:
        return []

    # Phân tích chuyên sâu cho lô bài chuẩn bị hiển thị
    try:
        analyzed_batch = analyze_papers(batch, topic)
    except Exception as exc:
        logger.error("Lỗi khi phân tích lô tải thêm: %s", exc)
        analyzed_batch = batch

    store.add_papers(analyzed_batch)
    return analyzed_batch


def analyze_single(paper: Paper, topic: str) -> Paper:
    """
    Phân tích một bài báo riêng lẻ bằng AI (dùng cho nút 'Tóm tắt bằng AI' khi bài chưa analyzed).

    Đầu vào:
        paper: Đối tượng Paper cần phân tích.
        topic: Đề tài nghiên cứu.

    Đầu ra:
        Đối tượng Paper đã được cập nhật tóm tắt và dữ liệu trích xuất.
    """
    try:
        results = analyze_papers([paper], topic)
        if results:
            return results[0]
    except Exception as exc:
        logger.error("Lỗi khi phân tích bài đơn lẻ: %s", exc)

    paper.analyzed = False
    return paper
