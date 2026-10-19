"""
Unit tests cho pipeline/search_pipeline.py bằng mock toàn bộ sources và ai_analysis.
Kiểm tra:
- Số lần gọi AI của run_first_search đúng 3 lần (build_keywords, score_papers, analyze_papers)
- Số lần gọi AI của load_more khi kho đủ đúng 1 lần (chỉ analyze_papers, không tìm kiếm mạng)
- load_more khi kho thiếu thì tăng offset, tìm trang tiếp và nạp thêm vào kho
- load_more không trả lại bài đã hiển thị
- Xử lý các bước AI lỗi mà không làm sập luồng
- Xử lý khi OpenAlex không trả bài nào
- analyze_single phân tích bài đơn lẻ
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from models.paper import Paper
from pipeline.search_pipeline import analyze_single, load_more, run_first_search
from selection.state import SelectionStore


@pytest.fixture
def store() -> SelectionStore:
    """Fixture cung cấp một SelectionStore sạch."""
    return SelectionStore()


def _make_dummy_papers(count: int, prefix: str = "paper") -> list[Paper]:
    return [
        Paper(
            doi=f"10.1000/{prefix}_{i}",
            title=f"Bài báo {prefix} {i}",
            year=2020 + (i % 5),
            abstract=f"Nội dung abstract đầy đủ của bài {i}...",
            citations=10 * i,
        )
        for i in range(1, count + 1)
    ]


def test_run_first_search_ai_calls_and_flow(store: SelectionStore) -> None:
    """Kiểm tra run_first_search gọi AI đúng 3 lần và phân phối đúng vào kho / hiển thị."""
    mock_keywords = {
        "primary_en": "digital trade economy",
        "en": ["ecommerce"],
        "vi": ["thương mại số"],
    }
    dummy_papers_en = _make_dummy_papers(15, prefix="en")
    dummy_papers_vi = _make_dummy_papers(5, prefix="vi")

    with (
        patch("pipeline.search_pipeline.build_keywords", return_value=mock_keywords) as mock_build_kw,
        patch("pipeline.search_pipeline.openalex.search", side_effect=[dummy_papers_en, dummy_papers_vi]) as mock_openalex,
        patch("pipeline.search_pipeline.score_papers", side_effect=lambda papers, topic: papers) as mock_score,
        patch("pipeline.search_pipeline.analyze_papers", side_effect=lambda papers, topic: papers) as mock_analyze,
    ):
        results = run_first_search("thương mại số", store, year_from=2020)

        # 1. Kiểm tra số lần gọi AI đúng 3 lần
        assert mock_build_kw.call_count == 1
        assert mock_score.call_count == 1
        assert mock_analyze.call_count == 1

        # 2. Kiểm tra OpenAlex được gọi 2 lần (en và vi)
        assert mock_openalex.call_count == 2

        # 3. Kết quả đợt đầu đúng 10 bài (FIRST_BATCH_SIZE)
        assert len(results) == 10
        assert len(store.get_all()) == 10

        # 4. Kho ứng viên còn lại 10 bài (20 - 10 = 10)
        assert store.pool_size() == 10
        assert store.topic == "thương mại số"


def test_load_more_when_pool_sufficient_calls_ai_once(store: SelectionStore) -> None:
    """Kiểm tra khi kho ứng viên đủ bài: không tìm kiếm mạng, chỉ gọi AI đúng 1 lần để analyze."""
    store.topic = "kinh tế tuần hoàn"
    store.keywords = {"primary_en": "circular economy", "vi": ["kinh tế tuần hoàn"]}
    pool_papers = _make_dummy_papers(10, prefix="pool")
    store.add_to_pool(pool_papers)

    with (
        patch("pipeline.search_pipeline.openalex.search") as mock_openalex,
        patch("pipeline.search_pipeline.score_papers") as mock_score,
        patch("pipeline.search_pipeline.analyze_papers", side_effect=lambda papers, topic: papers) as mock_analyze,
    ):
        results = load_more(store, year_from=2020)

        # Không gọi mạng và không gọi sàng lọc lại
        assert mock_openalex.call_count == 0
        assert mock_score.call_count == 0

        # Chỉ gọi AI đúng 1 lần để phân tích 5 bài lấy ra
        assert mock_analyze.call_count == 1
        assert len(results) == 5
        assert store.pool_size() == 5
        assert len(store.get_all()) == 5


def test_load_more_when_pool_insufficient_fetches_next_page(store: SelectionStore) -> None:
    """Kiểm tra khi kho ứng viên không đủ: tăng offset, tải trang kế tiếp từ nguồn, nạp pool và lấy đủ bài."""
    store.topic = "tăng trưởng xanh"
    store.keywords = {"primary_en": "green growth", "vi": ["tăng trưởng xanh"]}
    store.offsets = {"openalex_en": 1, "openalex_vi": 1}

    # Ban đầu trong kho chỉ có 2 bài
    initial_pool = _make_dummy_papers(2, prefix="init")
    store.add_to_pool(initial_pool)

    # Nguồn trả về thêm 10 bài ở trang 2
    new_papers = _make_dummy_papers(10, prefix="page2")

    with (
        patch("pipeline.search_pipeline.openalex.search", side_effect=[new_papers, []]) as mock_openalex,
        patch("pipeline.search_pipeline.score_papers", side_effect=lambda papers, topic: papers) as mock_score,
        patch("pipeline.search_pipeline.analyze_papers", side_effect=lambda papers, topic: papers) as mock_analyze,
    ):
        results = load_more(store, year_from=2020)

        # Kiểm tra đã gọi tìm kiếm mạng trang tiếp theo
        assert mock_openalex.call_count >= 1
        assert store.offsets["openalex_en"] == 2

        # Kiểm tra chấm điểm cho các bài mới
        assert mock_score.call_count == 1

        # Kết quả lấy đủ 5 bài (2 bài từ pool cũ + 3 bài từ trang mới)
        assert len(results) == 5
        assert mock_analyze.call_count == 1

        # Kho còn lại 7 bài mới (10 - 3 = 7)
        assert store.pool_size() == 7


def test_load_more_does_not_return_already_displayed_papers(store: SelectionStore) -> None:
    """Kiểm tra load_more không trả lại các bài đã hiển thị trước đó."""
    store.topic = "năng lượng tái tạo"
    store.keywords = {"primary_en": "renewable energy", "vi": []}

    # Giả sử đã hiển thị 5 bài
    old_papers = _make_dummy_papers(5, prefix="displayed")
    store.add_papers(old_papers)

    # Nguồn trả về danh sách chứa 2 bài cũ và 5 bài hoàn toàn mới
    new_papers = _make_dummy_papers(5, prefix="fresh")
    mixed_response = [old_papers[0], old_papers[1]] + new_papers

    with (
        patch("pipeline.search_pipeline.openalex.search", return_value=mixed_response),
        patch("pipeline.search_pipeline.score_papers", side_effect=lambda papers, topic: papers),
        patch("pipeline.search_pipeline.analyze_papers", side_effect=lambda papers, topic: papers),
    ):
        results = load_more(store, year_from=2020)

        displayed_dois = {p.doi for p in old_papers}
        result_dois = {p.doi for p in results}

        # Không có bài nào bị trùng với bài cũ
        assert displayed_dois.isdisjoint(result_dois)
        assert len(results) == 5


def test_ai_failure_resilience_in_run_first_search(store: SelectionStore) -> None:
    """Kiểm tra các bước AI bị lỗi thì luồng vẫn tiếp tục, bài vẫn được trả về và không crash."""
    dummy_papers = _make_dummy_papers(10, prefix="safe")

    with (
        patch("pipeline.search_pipeline.build_keywords", side_effect=RuntimeError("AI Error build_kw")),
        patch("pipeline.search_pipeline.openalex.search", return_value=dummy_papers),
        patch("pipeline.search_pipeline.score_papers", side_effect=RuntimeError("AI Error score")),
        patch("pipeline.search_pipeline.analyze_papers", side_effect=RuntimeError("AI Error analyze")),
    ):
        results = run_first_search("kinh tế lượng", store, year_from=2020)

        # Vẫn trả về 10 bài báo an toàn
        assert len(results) == 10
        assert len(store.get_all()) == 10


def test_run_first_search_empty_openalex(store: SelectionStore) -> None:
    """Kiểm tra khi nguồn không tìm thấy bài nào thì trả về danh sách rỗng, không crash."""
    with (
        patch("pipeline.search_pipeline.build_keywords", return_value={"primary_en": "rare topic", "vi": []}),
        patch("pipeline.search_pipeline.openalex.search", return_value=[]),
    ):
        results = run_first_search("rare topic", store, year_from=2020)
        assert results == []
        assert store.pool_size() == 0
        assert store.get_all() == []


def test_analyze_single() -> None:
    """Kiểm tra hàm analyze_single phân tích một bài báo riêng lẻ."""
    p = Paper(doi="10.1000/single", title="Bài đơn lẻ", abstract="Abstract đơn lẻ")

    def mock_analyze(papers: list[Paper], topic: str) -> list[Paper]:
        for paper in papers:
            paper.summary = "Đã phân tích đơn lẻ"
            paper.analyzed = True
        return papers

    with patch("pipeline.search_pipeline.analyze_papers", side_effect=mock_analyze):
        res = analyze_single(p, topic="Chủ đề đơn lẻ")
        assert res.summary == "Đã phân tích đơn lẻ"
        assert res.analyzed is True


def test_run_first_search_custom_batch_sizes(store: SelectionStore) -> None:
    """Kiểm tra run_first_search hỗ trợ các mức batch_size tùy chọn (5, 15, 20)."""
    mock_keywords = {
        "primary_en": "digital finance",
        "en": ["fintech"],
        "vi": ["tài chính số"],
    }
    dummy_papers = _make_dummy_papers(35, prefix="custom")

    # Kiểm tra mức 5 bài
    with (
        patch("pipeline.search_pipeline.build_keywords", return_value=mock_keywords),
        patch("pipeline.search_pipeline.openalex.search", side_effect=[dummy_papers, []]),
        patch("pipeline.search_pipeline.score_papers", side_effect=lambda papers, topic: papers),
        patch("pipeline.search_pipeline.analyze_papers", side_effect=lambda papers, topic: papers),
    ):
        results_5 = run_first_search("tài chính số", store, year_from=2020, batch_size=5)
        assert len(results_5) == 5
        assert len(store.get_all()) == 5
        assert store.pool_size() == 30
        assert store.target_count == 5

    # Kiểm tra mức 20 bài
    store.reset()
    with (
        patch("pipeline.search_pipeline.build_keywords", return_value=mock_keywords),
        patch("pipeline.search_pipeline.openalex.search", side_effect=[dummy_papers, []]),
        patch("pipeline.search_pipeline.score_papers", side_effect=lambda papers, topic: papers),
        patch("pipeline.search_pipeline.analyze_papers", side_effect=lambda papers, topic: papers),
    ):
        results_20 = run_first_search("tài chính số", store, year_from=2020, batch_size=20)
        assert len(results_20) == 20
        assert len(store.get_all()) == 20
        assert store.pool_size() == 15
        assert store.target_count == 20

