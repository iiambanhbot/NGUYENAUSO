"""
Unit tests cho selection/state.py.
Kiểm tra:
- Kho ứng viên (pool), pool_size
- take_from_pool lấy đúng thứ tự điểm giảm dần
- seen_keys và pool_keys
- Chọn bài (set_selected, get_selected) và ghi chú (set_note, set_reason)
- update_paper thay thế bài theo ID
- reset xóa sạch trạng thái
- get_store khởi tạo đúng singleton trong st.session_state
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
from models.paper import Paper
from selection.state import SelectionStore, get_store


def test_init_state() -> None:
    """Kiểm tra giá trị khởi tạo mặc định của SelectionStore."""
    store = SelectionStore()
    assert store.topic == ""
    assert store.keywords == {}
    assert store.pool == []
    assert store.offsets == {}
    assert store.get_all() == []
    assert store.pool_size() == 0
    assert store.seen_keys() == set()
    assert store.pool_keys() == set()
    assert store.target_count == 10


def test_pool_and_take_from_pool() -> None:
    """Kiểm tra thêm bài vào kho và lấy n bài điểm cao nhất ra khỏi kho."""
    store = SelectionStore()
    p1 = Paper(doi="10.1000/1", title="Bài 1", relevance_score=70, citations=10)
    p2 = Paper(doi="10.1000/2", title="Bài 2", relevance_score=95, citations=5)
    p3 = Paper(doi="10.1000/3", title="Bài 3", relevance_score=80, citations=20)
    p4 = Paper(doi="10.1000/4", title="Bài 4", relevance_score=85, citations=15)

    store.add_to_pool([p1, p2, p3, p4])
    assert store.pool_size() == 4
    assert p2.dedupe_key in store.pool_keys()

    # Lấy 2 bài cao điểm nhất (95 và 85)
    taken = store.take_from_pool(2)
    assert len(taken) == 2
    assert [p.relevance_score for p in taken] == [95, 85]
    assert store.pool_size() == 2

    # Các bài còn lại trong kho là 80 và 70
    remaining = store.take_from_pool(5)  # lấy nhiều hơn số lượng hiện có
    assert len(remaining) == 2
    assert [p.relevance_score for p in remaining] == [80, 70]
    assert store.pool_size() == 0


def test_seen_keys_and_add_papers() -> None:
    """Kiểm tra thêm bài vào danh sách hiển thị và lấy tập seen_keys."""
    store = SelectionStore()
    p1 = Paper(doi="10.1000/display1", title="Bài hiển thị 1")
    p2 = Paper(title="Paper Without DOI", year=2023)

    store.add_papers([p1, p2])
    all_papers = store.get_all()
    assert len(all_papers) == 2

    seen = store.seen_keys()
    assert p1.dedupe_key in seen
    assert p2.dedupe_key in seen


def test_selection_and_notes() -> None:
    """Kiểm tra đánh dấu chọn bài, lấy danh sách đã chọn và lưu ghi chú / lý do."""
    store = SelectionStore()
    p1 = Paper(doi="10.1000/p1", title="Bài số 1")
    p1.id = "10.1000/p1"

    p2 = Paper(doi="10.1000/p2", title="Bài số 2")
    p2.id = "10.1000/p2"

    store.add_papers([p1, p2])

    # Ban đầu chưa chọn bài nào
    assert store.get_selected() == []

    # Chọn bài 1
    store.set_selected("10.1000/p1", True)
    selected = store.get_selected()
    assert len(selected) == 1
    assert selected[0].doi == "10.1000/p1"

    # Ghi chú và lý do
    store.set_note("10.1000/p1", "Cần trích dẫn trong chương 2")
    store.set_reason("10.1000/p1", "Mô hình kinh tế lượng phù hợp")

    assert p1.notes == "Cần trích dẫn trong chương 2"
    assert p1.relevance_reason == "Mô hình kinh tế lượng phù hợp"
    assert store.notes["10.1000/p1"] == "Cần trích dẫn trong chương 2"
    assert store.reasons["10.1000/p1"] == "Mô hình kinh tế lượng phù hợp"

    # Bỏ chọn bài 1
    store.set_selected("10.1000/p1", False)
    assert store.get_selected() == []


def test_update_paper() -> None:
    """Kiểm tra thay thế cập nhật bài báo cùng ID khi AI hoàn thành tóm tắt."""
    store = SelectionStore()
    initial_p = Paper(doi="10.1000/update_me", title="Tiêu đề cũ", summary="")
    initial_p.id = "10.1000/update_me"

    store.add_papers([initial_p])

    updated_p = Paper(
        doi="10.1000/update_me",
        title="Tiêu đề đã chuẩn hóa",
        summary="Bản tóm tắt chi tiết do AI phân tích",
        analyzed=True,
    )
    updated_p.id = "10.1000/update_me"

    success = store.update_paper(updated_p)
    assert success is True

    current_papers = store.get_all()
    assert len(current_papers) == 1
    assert current_papers[0].title == "Tiêu đề đã chuẩn hóa"
    assert current_papers[0].summary == "Bản tóm tắt chi tiết do AI phân tích"
    assert current_papers[0].analyzed is True


def test_reset() -> None:
    """Kiểm tra phương thức reset xóa toàn bộ dữ liệu trạng thái."""
    store = SelectionStore()
    store.topic = "Kinh tế số"
    store.keywords = {"vi": ["kinh tế số"], "en": ["digital economy"]}
    store.offsets = {"openalex": 2}
    store.add_papers([Paper(doi="10.1000/reset", title="Bài test")])
    store.add_to_pool([Paper(doi="10.1000/pool_reset", title="Bài pool")])
    store.set_selected("10.1000/reset", True)
    store.set_note("10.1000/reset", "Note")

    store.reset()

    assert store.topic == ""
    assert store.keywords == {}
    assert store.offsets == {}
    assert store.get_all() == []
    assert store.pool_size() == 0
    assert store.get_selected() == []
    assert store.notes == {}
    assert store.reasons == {}
    assert store.target_count == 10


def test_get_store_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra get_store sử dụng st.session_state để duy trì duy nhất một SelectionStore."""
    fake_session_state: dict = {}
    mock_st = MagicMock()
    mock_st.session_state = fake_session_state
    monkeypatch.setitem(sys.modules, "streamlit", mock_st)

    store1 = get_store()
    assert isinstance(store1, SelectionStore)
    assert "selection_store" in fake_session_state

    # Lần 2 lấy lại cùng một đối tượng instance
    store2 = get_store()
    assert store1 is store2
