"""
Quản lý trạng thái phiên làm việc của người dùng trong ứng dụng Research Finder.
Đầu vào: Thao tác thêm bài báo, chọn bài, ghi chú, cập nhật tóm tắt và quản lý kho ứng viên.
Đầu ra: Trạng thái hiện tại gồm danh sách bài đang hiển thị, bài đã chọn và kho bài chờ hiển thị.
"""

from __future__ import annotations

from typing import Any, Optional

from merge.dedupe_rank import get_dedupe_key
from models.paper import Paper


def _is_paper(p: Any) -> bool:
    """Kiểm tra đối tượng có phải là Paper (chấp nhận cả trường hợp class được reload)."""
    return isinstance(p, Paper) or (hasattr(p, "title") and hasattr(p, "to_dict"))


class SelectionStore:
    """Lớp quản lý trạng thái phiên làm việc viết bằng Python thuần, không phụ thuộc Streamlit."""

    def __init__(self) -> None:
        self.topic: str = ""
        self.keywords: dict[str, Any] = {}
        self.pool: list[Paper] = []
        self.offsets: dict[str, int] = {}
        self._papers: list[Paper] = []
        self._selected_ids: set[str] = set()
        self.notes: dict[str, str] = {}
        self.reasons: dict[str, str] = {}
        self.roadmap: dict[str, Any] = {}
        self.roadmap_progress: dict[str, bool] = {}
        self.target_count: int = 10

    def add_papers(self, papers: list[Paper]) -> None:
        """
        Thêm các bài báo vào danh sách hiển thị, giữ nguyên thứ tự thêm.

        Đầu vào:
            papers: Danh sách các đối tượng Paper cần hiển thị.
        """
        if not papers:
            return
        for paper in papers:
            if _is_paper(paper):
                self._papers.append(paper)

    def get_all(self) -> list[Paper]:
        """
        Lấy toàn bộ danh sách các bài báo đã hiển thị.

        Đầu ra:
            Danh sách đối tượng Paper đang hiển thị theo thứ tự thêm.
        """
        return list(self._papers)

    def seen_keys(self) -> set[str]:
        """
        Lấy tập hợp dedupe_key của mọi bài báo đã hiển thị.

        Đầu ra:
            set các chuỗi dedupe_key.
        """
        keys: set[str] = set()
        for p in self._papers:
            k = p.dedupe_key if hasattr(p, "dedupe_key") else get_dedupe_key(p)
            if k:
                keys.add(k)
        return keys

    def pool_keys(self) -> set[str]:
        """
        Lấy tập hợp dedupe_key của mọi bài báo đang nằm trong kho ứng viên (chưa hiển thị).

        Đầu ra:
            set các chuỗi dedupe_key trong pool.
        """
        keys: set[str] = set()
        for p in self.pool:
            k = p.dedupe_key if hasattr(p, "dedupe_key") else get_dedupe_key(p)
            if k:
                keys.add(k)
        return keys

    def add_to_pool(self, papers: list[Paper]) -> None:
        """
        Thêm các bài báo vào kho ứng viên (tránh trùng lặp với bài đã hiển thị và bài đã có trong kho).

        Đầu vào:
            papers: Danh sách các bài báo ứng viên.
        """
        if not papers:
            return

        existing_keys = self.seen_keys() | self.pool_keys()
        for paper in papers:
            if not _is_paper(paper):
                continue
            k = paper.dedupe_key if hasattr(paper, "dedupe_key") else get_dedupe_key(paper)
            if k and k not in existing_keys:
                self.pool.append(paper)
                existing_keys.add(k)

    def pool_size(self) -> int:
        """
        Lấy số lượng bài báo hiện có trong kho ứng viên.

        Đầu ra:
            Số lượng bài báo trong pool.
        """
        return len(self.pool)

    def take_from_pool(self, n: int) -> list[Paper]:
        """
        Lấy n bài báo có điểm relevance_score cao nhất ra khỏi kho ứng viên (và xóa khỏi kho).
        Tiêu chí sắp xếp: relevance_score giảm dần -> citations giảm dần -> year giảm dần.

        Đầu vào:
            n: Số lượng bài cần lấy.

        Đầu ra:
            Danh sách tối đa n bài báo có điểm cao nhất.
        """
        if n <= 0 or not self.pool:
            return []

        def sort_key(p: Paper) -> tuple[int, int, int, int]:
            score = p.relevance_score or 0
            has_score = 1 if score > 0 else 0
            cit = getattr(p, "citation_count", p.citations) or 0
            year = p.year or 0
            return (-has_score, -score, -cit, -year)

        sorted_pool = sorted(self.pool, key=sort_key)
        taken = sorted_pool[:n]
        self.pool = sorted_pool[n:]
        return taken

    def _match_paper_id(self, paper: Paper, target_id: str) -> bool:
        """Kiểm tra bài báo có khớp với định danh target_id hay không."""
        p_id = getattr(paper, "id", "") or ""
        p_doi = getattr(paper, "doi", "") or ""
        p_key = paper.dedupe_key if hasattr(paper, "dedupe_key") else get_dedupe_key(paper)
        return target_id in (p_id, p_doi, p_key)

    def set_selected(self, paper_id: str, value: bool = True) -> None:
        """
        Đặt trạng thái được chọn/bỏ chọn cho bài báo.

        Đầu vào:
            paper_id: Định danh của bài báo (id, doi hoặc dedupe_key).
            value: True nếu chọn, False nếu bỏ chọn.
        """
        if value:
            self._selected_ids.add(paper_id)
        else:
            self._selected_ids.discard(paper_id)

    def get_selected(self) -> list[Paper]:
        """
        Lấy danh sách các đối tượng Paper đang được người dùng đánh dấu chọn.

        Đầu ra:
            Danh sách đối tượng Paper đã chọn từ danh sách đang hiển thị.
        """
        selected_papers: list[Paper] = []
        for p in self._papers:
            p_id = getattr(p, "id", "") or ""
            p_doi = getattr(p, "doi", "") or ""
            p_key = p.dedupe_key if hasattr(p, "dedupe_key") else get_dedupe_key(p)
            if (
                p_id in self._selected_ids
                or p_doi in self._selected_ids
                or p_key in self._selected_ids
            ):
                selected_papers.append(p)
        return selected_papers

    def set_note(self, paper_id: str, note: str) -> None:
        """
        Lưu ghi chú của người dùng cho bài báo.

        Đầu vào:
            paper_id: Định danh của bài báo.
            note: Nội dung ghi chú.
        """
        self.notes[paper_id] = note
        for p in self._papers:
            if self._match_paper_id(p, paper_id):
                p.notes = note
        for p in self.pool:
            if self._match_paper_id(p, paper_id):
                p.notes = note

    def set_reason(self, paper_id: str, reason: str) -> None:
        """
        Lưu lý do đánh giá độ phù hợp của bài báo.

        Đầu vào:
            paper_id: Định danh của bài báo.
            reason: Nội dung lý do đánh giá.
        """
        self.reasons[paper_id] = reason
        for p in self._papers:
            if self._match_paper_id(p, paper_id):
                p.relevance_reason = reason
        for p in self.pool:
            if self._match_paper_id(p, paper_id):
                p.relevance_reason = reason

    def update_paper(self, paper: Paper) -> bool:
        """
        Thay thế bài báo có cùng định danh trong danh sách hiển thị (dùng khi AI bổ sung tóm tắt chuyên sâu).

        Đầu vào:
            paper: Đối tượng Paper mới chứa thông tin cập nhật.

        Đầu ra:
            True nếu tìm thấy và cập nhật thành công, False nếu không tìm thấy.
        """
        if not _is_paper(paper):
            return False

        updated = False
        target_id = getattr(paper, "id", "") or getattr(paper, "doi", "")
        target_key = paper.dedupe_key if hasattr(paper, "dedupe_key") else get_dedupe_key(paper)

        for i, existing in enumerate(self._papers):
            ex_id = getattr(existing, "id", "") or getattr(existing, "doi", "")
            ex_key = existing.dedupe_key if hasattr(existing, "dedupe_key") else get_dedupe_key(existing)
            if (target_id and ex_id == target_id) or (target_key and ex_key == target_key):
                self._papers[i] = paper
                updated = True
                break

        return updated

    def set_roadmap(self, roadmap: dict[str, Any]) -> None:
        """
        Lưu đối tượng lộ trình nghiên cứu và khởi tạo trạng thái tiến trình cho các bước.

        Đầu vào:
            roadmap: Dữ liệu lộ trình do AI sinh ra hoặc từ template.
        """
        self.roadmap = roadmap or {}
        # Đảm bảo mỗi bước trong roadmap có 1 entry trạng thái
        for phase in self.roadmap.get("phases", []):
            for step in phase.get("steps", []):
                sid = step.get("id")
                if sid and sid not in self.roadmap_progress:
                    self.roadmap_progress[sid] = False

    def set_step_progress(self, step_id: str, completed: bool) -> None:
        """
        Cập nhật trạng thái hoàn thành cho một bước nghiên cứu.

        Đầu vào:
            step_id: Mã định danh của bước (ví dụ: step_1_1).
            completed: True nếu đã hoàn thành, False nếu chưa.
        """
        self.roadmap_progress[step_id] = bool(completed)

    def get_step_progress(self, step_id: str) -> bool:
        """Kiểm tra một bước nghiên cứu đã hoàn thành hay chưa."""
        return bool(self.roadmap_progress.get(step_id, False))

    def get_roadmap_stats(self) -> dict[str, int]:
        """
        Thống kê tổng số bước và tỷ lệ phần trăm hoàn thành của lộ trình nghiên cứu.

        Đầu ra:
            dict chứa total, completed, percent.
        """
        all_step_ids: list[str] = []
        for phase in self.roadmap.get("phases", []):
            for step in phase.get("steps", []):
                sid = step.get("id")
                if sid:
                    all_step_ids.append(sid)

        total = len(all_step_ids)
        if total == 0:
            return {"total": 0, "completed": 0, "percent": 0}

        completed = sum(1 for sid in all_step_ids if self.roadmap_progress.get(sid, False))
        percent = int((completed / total) * 100)
        return {"total": total, "completed": completed, "percent": percent}

    def reset_roadmap_progress(self) -> None:
        """Đặt lại toàn bộ các bước nghiên cứu về trạng thái chưa hoàn thành."""
        for k in self.roadmap_progress:
            self.roadmap_progress[k] = False

    def __getattr__(self, name: str) -> Any:
        """Hỗ trợ fallback an toàn khi Streamlit lưu trữ instance cũ trước khi cập nhật code."""
        if name == "roadmap":
            self.roadmap = {}
            return self.roadmap
        if name == "roadmap_progress":
            self.roadmap_progress = {}
            return self.roadmap_progress
        if name == "target_count":
            self.target_count = 10
            return self.target_count
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def reset(self) -> None:
        """Xóa toàn bộ dữ liệu và đưa trạng thái về mặc định ban đầu."""
        self.topic = ""
        self.keywords = {}
        self.pool.clear()
        self.offsets.clear()
        self._papers.clear()
        self._selected_ids.clear()
        self.notes.clear()
        self.reasons.clear()
        self.roadmap = {}
        self.roadmap_progress.clear()
        self.target_count = 10


def get_store() -> SelectionStore:
    """
    Lấy hoặc khởi tạo instance SelectionStore duy nhất lưu trong st.session_state.

    Đầu ra:
        Đối tượng SelectionStore dùng chung cho toàn bộ phiên người dùng.
    """
    import streamlit as st

    if "selection_store" not in st.session_state:
        st.session_state["selection_store"] = SelectionStore()
    else:
        existing = st.session_state["selection_store"]
        if not hasattr(existing, "set_roadmap"):
            new_store = SelectionStore()
            for k in ("topic", "keywords", "pool", "offsets", "_papers", "_selected_ids", "notes", "reasons", "target_count"):
                if hasattr(existing, k):
                    setattr(new_store, k, getattr(existing, k))
            if hasattr(existing, "roadmap"):
                new_store.roadmap = getattr(existing, "roadmap")
            if hasattr(existing, "roadmap_progress"):
                new_store.roadmap_progress = getattr(existing, "roadmap_progress")
            st.session_state["selection_store"] = new_store

    store = st.session_state["selection_store"]
    if not hasattr(store, "roadmap") or store.roadmap is None:
        store.roadmap = {}
    if not hasattr(store, "roadmap_progress") or store.roadmap_progress is None:
        store.roadmap_progress = {}
    if not hasattr(store, "target_count") or store.target_count is None:
        store.target_count = 10
    return store
