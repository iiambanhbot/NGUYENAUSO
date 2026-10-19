"""
Unit tests cho các phương thức quản lý lộ trình và tiến trình trong SelectionStore.
Kiểm tra:
- set_roadmap khởi tạo danh sách tiến trình
- set_step_progress và get_step_progress
- get_roadmap_stats tính chính xác tổng số, hoàn thành và phần trăm
- reset_roadmap_progress đặt lại toàn bộ bước
- reset xóa sạch dữ liệu cả roadmap
"""

from __future__ import annotations

import pytest
from selection.state import SelectionStore


def test_roadmap_state_flow() -> None:
    """Kiểm tra toàn bộ chu trình lưu lộ trình và tích chọn tiến trình."""
    store = SelectionStore()
    assert store.roadmap == {}
    assert store.roadmap_progress == {}
    assert store.get_roadmap_stats() == {"total": 0, "completed": 0, "percent": 0}

    mock_roadmap = {
        "phases": [
            {
                "phase_id": "P1",
                "steps": [
                    {"id": "step_1_1", "title": "Bước 1.1"},
                    {"id": "step_1_2", "title": "Bước 1.2"},
                ],
            },
            {
                "phase_id": "P2",
                "steps": [
                    {"id": "step_2_1", "title": "Bước 2.1"},
                    {"id": "step_2_2", "title": "Bước 2.2"},
                ],
            },
        ]
    }

    store.set_roadmap(mock_roadmap)
    assert len(store.roadmap_progress) == 4
    assert store.get_step_progress("step_1_1") is False

    stats = store.get_roadmap_stats()
    assert stats["total"] == 4
    assert stats["completed"] == 0
    assert stats["percent"] == 0

    # Tích hoàn thành 2 bước (step_1_1 và step_2_1) -> 50%
    store.set_step_progress("step_1_1", True)
    store.set_step_progress("step_2_1", True)
    assert store.get_step_progress("step_1_1") is True
    assert store.get_step_progress("step_2_1") is True
    assert store.get_step_progress("step_1_2") is False

    stats2 = store.get_roadmap_stats()
    assert stats2["completed"] == 2
    assert stats2["percent"] == 50

    # Bỏ chọn step_2_1
    store.set_step_progress("step_2_1", False)
    stats3 = store.get_roadmap_stats()
    assert stats3["completed"] == 1
    assert stats3["percent"] == 25

    # Đặt lại tiến trình
    store.reset_roadmap_progress()
    assert store.get_step_progress("step_1_1") is False
    assert store.get_roadmap_stats()["completed"] == 0

    # Reset store
    store.reset()
    assert store.roadmap == {}
    assert store.roadmap_progress == {}
