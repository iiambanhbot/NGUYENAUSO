"""
Giao diện hiển thị một ô bài báo nghiên cứu kinh tế (Paper Card).
Đầu vào: Đối tượng Paper và SelectionStore.
Đầu ra: Render giao diện thẻ bài báo với expander, link, tóm tắt, checkbox và ghi chú.
"""

from __future__ import annotations

import hashlib
import streamlit as st

from models.paper import Paper
from pipeline.search_pipeline import analyze_single
from selection.state import SelectionStore


def _get_safe_key(paper_id: str) -> str:
    """Tạo key hợp lệ và duy nhất cho Streamlit widgets."""
    clean_id = str(paper_id or "").strip()
    if not clean_id:
        return "empty_id"
    return hashlib.md5(clean_id.encode("utf-8")).hexdigest()[:16]


def render_paper_card(
    paper: Paper,
    store: SelectionStore,
    index: int | None = None,
) -> None:
    """
    Render giao diện một ô bài báo nghiên cứu chuẩn học thuật chuyên nghiệp.

    - Header thẻ: Thứ tự bài, năm xuất bản, nhãn Open Access, số trích dẫn, điểm phù hợp.
    - Tiêu đề an toàn không lỗi markdown, mở link tab mới.
    - Tác giả & Tạp chí xuất bản.
    - Tóm lược AI hoặc preview abstract với nút bấm Tóm tắt bằng AI tích hợp ngay trong thẻ.
    - Expander thông tin chi tiết: Tóm tắt đầy đủ, phương pháp, mẫu, biến, quốc gia, kết quả, hàm ý.
    """
    paper_id = getattr(paper, "id", "") or getattr(paper, "doi", "") or paper.title
    safe_key = _get_safe_key(paper_id)

    title = paper.title or "Không có tiêu đề"
    year_str = str(paper.year) if paper.year is not None else "N/A"
    url = getattr(paper, "url", "") or (f"https://doi.org/{paper.doi}" if paper.doi else "")

    # Xác định trạng thái đã chọn
    selected_papers = store.get_selected()
    is_selected = (
        paper in selected_papers
        or paper_id in store._selected_ids
        or getattr(paper, "doi", "") in store._selected_ids
    )

    with st.container(border=True):
        # 1. Hàng trên: Huy hiệu & Checkbox chọn bài
        col_badges, col_check = st.columns([0.76, 0.24])

        with col_badges:
            badge_htmls: list[str] = []
            if index is not None:
                badge_htmls.append(f'<span class="rf-badge rf-badge-idx">Bài #{index}</span>')
            badge_htmls.append(f'<span class="rf-badge rf-badge-year">📅 {year_str}</span>')

            # Huy hiệu Open Access
            if getattr(paper, "is_open_access", False):
                oa_url = getattr(paper, "open_access_url", "")
                if oa_url:
                    badge_htmls.append(
                        f'<a href="{oa_url}" target="_blank" rel="noopener noreferrer" class="rf-badge rf-badge-oa">🔓 Open Access ↗</a>'
                    )
                else:
                    badge_htmls.append('<span class="rf-badge rf-badge-oa">🔓 Open Access</span>')

            # Số trích dẫn
            citations = getattr(paper, "citation_count", paper.citations)
            if citations:
                badge_htmls.append(f'<span class="rf-badge rf-badge-cite">⭐ {citations} trích dẫn</span>')

            # Điểm phù hợp (relevance score nếu có)
            rel_score = getattr(paper, "relevance_score", 0)
            if rel_score and rel_score > 0:
                badge_htmls.append(f'<span class="rf-badge rf-badge-score">🎯 Phù hợp: {rel_score}%</span>')

            st.markdown(f'<div class="rf-badge-row">{"".join(badge_htmls)}</div>', unsafe_allow_html=True)

        with col_check:
            checked = st.checkbox(
                "Chọn bài này",
                value=is_selected,
                key=f"chk_outer_{safe_key}",
                help="Tích chọn bài báo để đưa vào danh sách xuất Excel",
            )
            if checked != is_selected:
                store.set_selected(paper_id, checked)
                st.rerun()

        # 2. Tiêu đề bài báo nổi bật và an toàn
        safe_title = (
            title.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        if url:
            st.markdown(
                f"<h4 style='margin: 0.2rem 0 0.4rem 0;'><a href='{url}' target='_blank' rel='noopener noreferrer' class='rf-paper-title-link'>{safe_title} 🔗</a></h4>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"<h4 style='margin: 0.2rem 0 0.4rem 0;' class='rf-paper-title-text'>{safe_title}</h4>", unsafe_allow_html=True)

        # 3. Tác giả & Tạp chí xuất bản
        meta_sub: list[str] = []
        if paper.authors:
            authors_str = ", ".join(paper.authors[:4])
            if len(paper.authors) > 4:
                authors_str += " et al."
            meta_sub.append(f'<span class="rf-meta-item">👤 {authors_str}</span>')

        venue = getattr(paper, "venue", paper.journal)
        if venue:
            meta_sub.append(f'<span class="rf-meta-item rf-meta-venue">🏛️ <em>{venue}</em></span>')

        if paper.doi:
            meta_sub.append(f'<span class="rf-meta-item rf-meta-doi">DOI: {paper.doi}</span>')

        if meta_sub:
            st.markdown(f'<div class="rf-meta-row">{" • ".join(meta_sub)}</div>', unsafe_allow_html=True)

        # 4. Tóm tắt nhanh & Nút Tóm tắt bằng AI (nếu chưa tóm tắt)
        short_summary = getattr(paper, "summary", "") or getattr(paper, "short_summary", "")
        limitations = getattr(paper, "limitations", "").strip()

        if short_summary:
            safe_summary = (
                short_summary.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            st.markdown(
                f"""
                <div class="rf-ai-box">
                    <div class="rf-ai-header">
                        <span>✨</span>
                        <span>Tóm lược AI chuyên sâu</span>
                    </div>
                    <div class="rf-ai-text">{safe_summary}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            lim_display = limitations if limitations else "Chưa nêu rõ trong abstract"
            safe_lim = (
                lim_display.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            st.markdown(
                f"""
                <div class="rf-limitation-box">
                    <span class="rf-limitation-label">⚠️ Hạn chế đối với đề tài:</span>
                    <span class="rf-limitation-val">{safe_lim}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            abstract = paper.abstract or ""
            if abstract:
                col_abs_text, col_abs_btn = st.columns([0.74, 0.26])
                with col_abs_text:
                    preview = (abstract[:280] + "...") if len(abstract) > 280 else abstract
                    safe_preview = (
                        preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    )
                    st.markdown(
                        f"""
                        <div class="rf-abstract-preview">
                            <span class="rf-abs-label">📄 Tóm tắt gốc:</span> {safe_preview} 
                            <span class="rf-abs-pending">(Chưa phân tích bằng AI)</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_abs_btn:
                    if st.button("🤖 Tóm tắt bằng AI", key=f"btn_ai_{safe_key}", use_container_width=True):
                        try:
                            with st.spinner("Đang phân tích..."):
                                updated_p = analyze_single(paper, store.topic)
                                store.update_paper(updated_p)
                                if not getattr(updated_p, "analyzed", False):
                                    st.warning("Hết hạn mức hoặc chưa cấu hình API key.")
                                st.rerun()
                        except Exception as exc:
                            st.warning(f"Lỗi AI: {exc}")
            else:
                st.caption(":gray[Chưa có tóm tắt • Chưa phân tích bằng AI]")

        # 5. Khung expander chi tiết học thuật & trích xuất dữ liệu
        short_t = f"{title[:65]}..." if len(title) > 65 else title
        with st.expander(f"🔍 Xem chi tiết: {short_t} ({year_str})", expanded=False):
            # Tóm tắt chi tiết (detail_summary)
            detail_summary = (
                getattr(paper, "detail_summary", "")
                or getattr(paper, "summary", "")
                or paper.abstract
            )
            if detail_summary:
                st.markdown("##### 📝 Tóm tắt nội dung đầy đủ")
                st.write(detail_summary)

            # Data trích xuất học thuật
            extracted_items: list[tuple[str, str, str]] = []

            if paper.methodology:
                extracted_items.append(("🔬", "Phương pháp nghiên cứu", paper.methodology))

            sample_data = getattr(paper, "data_source", "") or getattr(paper, "sample", "")
            if sample_data:
                extracted_items.append(("📊", "Dữ liệu & Mẫu nghiên cứu", sample_data))

            variables = getattr(paper, "variables", "")
            if variables:
                extracted_items.append(("📈", "Biến số nghiên cứu", variables))

            country = getattr(paper, "country", "")
            if country:
                extracted_items.append(("🌍", "Quốc gia & Địa bàn", country))

            if paper.key_findings:
                extracted_items.append(("🎯", "Kết quả phát hiện chính", paper.key_findings))

            lim_detail = getattr(paper, "limitations", "").strip() or "Chưa nêu rõ trong abstract"
            extracted_items.append(("⚠️", "Hạn chế đối với đề tài", lim_detail))

            if getattr(paper, "policy_implications", ""):
                extracted_items.append(("🏛️", "Hàm ý chính sách & Thực tiễn", paper.policy_implications))

            if getattr(paper, "relevance_reason", ""):
                extracted_items.append(("💡", "Lý do phù hợp với đề tài", paper.relevance_reason))

            if extracted_items:
                st.markdown("##### 📊 Dữ liệu trích xuất chuyên sâu")
                for icon, label, val in extracted_items:
                    st.markdown(f"- {icon} **{label}:** {val}")

            # Ghi "Dựa trên abstract" khi extracted_data.basis == "abstract"
            extracted_data_obj = getattr(paper, "extracted_data", None)
            basis = getattr(extracted_data_obj, "basis", "") or getattr(paper, "basis", "")
            if basis == "abstract":
                st.caption("ℹ️ *Dữ liệu trích xuất được AI phân tích dựa trên abstract của bài báo.*")

            st.markdown("---")
            # Ghi chú cá nhân và lý do chọn bài
            col_in_1, col_in_2 = st.columns(2)
            with col_in_1:
                current_note = store.notes.get(paper_id, paper.notes or "")
                new_note = st.text_input(
                    "📌 Ghi chú cá nhân:",
                    value=current_note,
                    key=f"note_{safe_key}",
                    placeholder="Nhập ghi chú quan trọng...",
                )
                if new_note != current_note:
                    store.set_note(paper_id, new_note)

            with col_in_2:
                current_reason = store.reasons.get(paper_id, paper.relevance_reason or "")
                new_reason = st.text_input(
                    "💡 Lý do lựa chọn bài:",
                    value=current_reason,
                    key=f"reason_{safe_key}",
                    placeholder="Ví dụ: mô hình thực nghiệm phù hợp...",
                )
                if new_reason != current_reason:
                    store.set_reason(paper_id, new_reason)
