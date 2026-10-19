"""
Giao diện Trang Đề xuất Lộ trình Nghiên cứu Khoa học (Research Roadmap & Progress Tracker).
Đầu vào: SelectionStore (lưu đề tài, bài báo đã chọn, trạng thái lộ trình và checklist).
Đầu ra: Render giao diện sơ đồ quy trình Mermaid và bảng đánh dấu tiến trình tương tác.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from ai_analysis.roadmap_builder import generate_research_roadmap
from selection.state import SelectionStore


def _render_mermaid_diagram(mermaid_code: str, height: int = 380) -> None:
    """
    Render sơ đồ Mermaid với giao diện Dark Mode chuẩn mực bằng Mermaid.js CDN.
    Đảm bảo tương thích hoàn hảo và hiển thị sắc nét trên mọi trình duyệt.
    """
    if not mermaid_code or not mermaid_code.strip():
        st.info("Chưa có mã sơ đồ quy trình.")
        return

    # Làm sạch mã để nhúng an toàn vào HTML
    escaped_code = (
        mermaid_code.strip()
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("$", "\\$")
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <style>
            body {{
                margin: 0;
                padding: 12px;
                background-color: transparent;
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                overflow-x: auto;
            }}
            .mermaid {{
                display: flex;
                justify-content: center;
                width: 100%;
            }}
            .mermaid svg {{
                max-width: 100%;
                height: auto;
                filter: drop-shadow(0 4px 12px rgba(0,0,0,0.3));
            }}
        </style>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{
                startOnLoad: true,
                theme: 'dark',
                themeVariables: {{
                    darkMode: true,
                    background: '#0b1120',
                    primaryColor: '#1e293b',
                    primaryTextColor: '#f8fafc',
                    primaryBorderColor: '#3b82f6',
                    lineColor: '#60a5fa',
                    secondaryColor: '#0f172a',
                    tertiaryColor: '#1e1b4b',
                    mainBkg: '#0f172a',
                    nodeBorder: '#3b82f6'
                }},
                flowchart: {{
                    curve: 'basis',
                    padding: 16,
                    nodeSpacing: 45,
                    rankSpacing: 45
                }}
            }});
        </script>
    </head>
    <body>
        <div class="mermaid">
{mermaid_code.strip()}
        </div>
    </body>
    </html>
    """

    components.html(html_content, height=height, scrolling=True)


def _export_roadmap_markdown(roadmap: dict, store: SelectionStore) -> str:
    """Tạo nội dung Markdown đầy đủ của lộ trình và tiến trình để người dùng tải về."""
    topic = roadmap.get("topic", store.topic) or "Đề tài NCKH"
    rtype = roadmap.get("research_type", "Chưa phân loại")
    overview = roadmap.get("overview", "")
    questions = roadmap.get("research_questions", [])
    phases = roadmap.get("phases", [])
    stats = store.get_roadmap_stats()

    lines = [
        f"# KẾ HOẠCH & TIẾN TRÌNH NGHIÊN CỨU KHOA HỌC",
        f"**Đề tài:** {topic}",
        f"**Định hướng nghiên cứu:** {rtype}",
        f"**Tiến độ hiện tại:** {stats['completed']}/{stats['total']} bước ({stats['percent']}%)",
        "",
        "## 1. TỔNG QUAN HƯỚNG TIẾP CẬN",
        overview,
        "",
        "## 2. CÂU HỎI NGHIÊN CỨU TRỌNG TÂM",
    ]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q}")

    lines.extend(["", "## 3. SƠ ĐỒ QUY TRÌNH NGHIÊN CỨU (MERMAID)", "```mermaid", roadmap.get("mermaid_code", ""), "```", ""])
    lines.extend(["## 4. BẢNG TIẾN TRÌNH & NHIỆM VỤ CHI TIẾT", ""])

    for phase in phases:
        lines.append(f"### {phase.get('phase_name', 'Giai đoạn')}")
        if phase.get("description"):
            lines.append(f"*{phase.get('description')}*")
        lines.append("")
        for step in phase.get("steps", []):
            sid = step.get("id", "")
            done = store.get_step_progress(sid)
            mark = "[x]" if done else "[ ]"
            title = step.get("title", "")
            tasks = step.get("tasks", "")
            deliv = step.get("deliverable", "")
            tool = step.get("tools_tips", "")
            lines.append(f"- {mark} **{title}**")
            lines.append(f"  - **Nhiệm vụ:** {tasks}")
            lines.append(f"  - **Sản phẩm đầu ra:** {deliv}")
            if tool:
                lines.append(f"  - **Công cụ / Gợi ý:** {tool}")
        lines.append("")

    return "\n".join(lines)


def render_roadmap_page(store: SelectionStore) -> None:
    """
    Render toàn bộ trang Đề xuất Lộ trình Nghiên cứu & Bảng theo dõi tiến độ.
    """
    if not hasattr(store, "roadmap") or store.roadmap is None:
        store.roadmap = {}
    if not hasattr(store, "roadmap_progress") or store.roadmap_progress is None:
        store.roadmap_progress = {}

    # Đảm bảo đầy đủ 100% các phương thức dù là instance cũ
    if not hasattr(store, "set_roadmap"):
        def _set_rm(rm: dict) -> None:
            store.roadmap = rm or {}
            for phase in store.roadmap.get("phases", []):
                for step in phase.get("steps", []):
                    sid = step.get("id")
                    if sid and sid not in store.roadmap_progress:
                        store.roadmap_progress[sid] = False
        setattr(store, "set_roadmap", _set_rm)

    if not hasattr(store, "set_step_progress"):
        setattr(store, "set_step_progress", lambda sid, val: store.roadmap_progress.__setitem__(sid, bool(val)))

    if not hasattr(store, "get_step_progress"):
        setattr(store, "get_step_progress", lambda sid: bool(store.roadmap_progress.get(sid, False)))

    if not hasattr(store, "get_roadmap_stats"):
        def _get_rs() -> dict[str, int]:
            all_sids = [s.get("id") for p in store.roadmap.get("phases", []) for s in p.get("steps", []) if s.get("id")]
            total = len(all_sids)
            if total == 0:
                return {"total": 0, "completed": 0, "percent": 0}
            done = sum(1 for sid in all_sids if store.roadmap_progress.get(sid, False))
            return {"total": total, "completed": done, "percent": int((done / total) * 100)}
        setattr(store, "get_roadmap_stats", _get_rs)

    if not hasattr(store, "reset_roadmap_progress"):
        def _rst_rp() -> None:
            for k in store.roadmap_progress:
                store.roadmap_progress[k] = False
        setattr(store, "reset_roadmap_progress", _rst_rp)

    st.markdown(
        """
        <div class="rf-roadmap-banner">
            <div class="rf-roadmap-banner-glow"></div>
            <div style="position: relative; z-index: 1;">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                    <span style="font-size: 1.5rem;">🗺️</span>
                    <h3 style="margin: 0; font-size: 1.35rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.01em;">
                        Đề xuất Lộ trình & Kế hoạch Nghiên cứu Khoa học
                    </h3>
                    <span class="rf-banner-pill" style="margin-left: 6px;">AI Methodology</span>
                </div>
                <div style="color: #94a3b8; font-size: 0.9rem; line-height: 1.5;">
                    Xây dựng quy trình nghiên cứu từng bước, trực quan hóa sơ đồ luồng thực hiện và bảng đánh dấu tiến trình thực tế cho đề tài của bạn.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. KHUNG THIẾT LẬP ĐỀ TÀI & KHỞI TẠO LỘ TRÌNH
    with st.container(border=True):
        st.markdown("#### 🎯 Thiết lập thông số đề tài")

        col_t1, col_t2 = st.columns([0.65, 0.35])
        with col_t1:
            current_topic = store.topic or ""
            target_topic = st.text_input(
                "Chủ đề nghiên cứu cần lập lộ trình:",
                value=current_topic,
                placeholder="Ví dụ: Tác động của chuyển đổi số đến hiệu quả ngân hàng thương mại Việt Nam...",
                help="Tự động đồng bộ với đề tài bạn đang tìm kiếm ở trang Tìm tài liệu, hoặc bạn có thể nhập đề tài mới bất kỳ.",
            )
        with col_t2:
            research_type = st.selectbox(
                "Định hướng phương pháp nghiên cứu:",
                options=[
                    "Định lượng (Quantitative - Kinh tế lượng, Mô hình dữ liệu bảng, GMM)",
                    "Khảo sát & Mô hình cấu trúc (Survey - PLS-SEM, CFA, SPSS)",
                    "Tổng quan hệ thống & Phân tích tổng hợp (SLR - PRISMA, Meta-analysis)",
                    "Định tính (Qualitative - Phỏng vấn sâu, Nghiên cứu trường hợp Case study)",
                    "Hỗn hợp (Mixed Methods - Kết hợp Định tính & Định lượng)",
                ],
                index=0,
                help="Lựa chọn định hướng phương pháp để AI thiết kế các bước và công cụ tương ứng chuẩn mực nhất.",
            )

        col_btn1, col_btn2, col_spacer = st.columns([0.28, 0.24, 0.48])
        with col_btn1:
            btn_generate = st.button("✨ Khởi tạo lộ trình bằng AI", type="primary", use_container_width=True)
        with col_btn2:
            current_rm = getattr(store, "roadmap", {}) or {}
            has_roadmap = bool(current_rm and current_rm.get("phases"))
            btn_reset_prog = st.button("🔄 Đặt lại tiến trình", disabled=not has_roadmap, use_container_width=True)

        if btn_reset_prog:
            if hasattr(store, "reset_roadmap_progress"):
                store.reset_roadmap_progress()
            st.success("Đã đặt lại toàn bộ đánh dấu tiến trình!")
            st.rerun()

        if btn_generate:
            if not target_topic.strip():
                st.warning("Vui lòng nhập đề tài nghiên cứu ở ô bên trên.")
            else:
                with st.spinner("Đang phân tích phương pháp luận và lập lộ trình nghiên cứu bằng AI..."):
                    try:
                        # Đồng bộ đề tài vào store nếu chưa có
                        if not store.topic:
                            store.topic = target_topic.strip()

                        # Lấy danh sách bài báo đã chọn (hoặc đã hiển thị) làm cơ sở tham chiếu
                        ref_papers = store.get_selected() or store.get_all()[:6]
                        new_roadmap = generate_research_roadmap(
                            topic=target_topic.strip(),
                            research_type=research_type,
                            papers=ref_papers,
                            use_cache=False,  # Bấm nút tạo mới thì không đọc cache cũ
                        )
                        store.set_roadmap(new_roadmap)
                        st.success("Đã khởi tạo lộ trình nghiên cứu thành công!")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Lỗi khi khởi tạo lộ trình: {exc}")

    # Kiểm tra xem đã có roadmap hay chưa
    roadmap = getattr(store, "roadmap", {}) or {}
    if not roadmap or not roadmap.get("phases"):
        # Nếu chưa có roadmap nhưng đã có đề tài ở store, tự động tạo roadmap mẫu ban đầu
        if store.topic:
            auto_rm = generate_research_roadmap(
                topic=store.topic,
                research_type="Định lượng (Quantitative)",
                papers=store.get_selected(),
                use_cache=True,
            )
            store.set_roadmap(auto_rm)
            roadmap = store.roadmap
        else:
            st.markdown(
                """
                <div class="rf-empty-search-card" style="margin-top: 1.2rem;">
                    <div class="rf-empty-icon">🗺️</div>
                    <div class="rf-empty-title">Chưa có lộ trình nghiên cứu</div>
                    <div class="rf-empty-sub">
                        Hãy nhập đề tài ở khung trên hoặc thực hiện tìm kiếm bài báo ở trang <strong>Tìm tài liệu</strong>, 
                        sau đó bấm nút <strong>✨ Khởi tạo lộ trình bằng AI</strong> để tạo sơ đồ các bước và bảng tiến trình.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

    # 2. KHUNG THỐNG KÊ TIẾN ĐỘ TỔNG QUAN
    stats = store.get_roadmap_stats()
    total_steps = stats["total"]
    completed_steps = stats["completed"]
    pct = stats["percent"]

    st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 8px;">
                <div>
                    <span style="font-size: 1.1rem; font-weight: 700; color: #f8fafc;">📊 Tiến độ thực hiện nghiên cứu</span>
                    <span style="font-size: 0.88rem; color: #94a3b8; margin-left: 8px;">({completed_steps}/{total_steps} bước hoàn thành)</span>
                </div>
                <div style="font-size: 1.35rem; font-weight: 800; color: #38bdf8; font-variant-numeric: tabular-nums;">
                    {pct}%
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(pct / 100.0)

        # Thanh thông tin tổng quan & câu hỏi nghiên cứu
        overview = roadmap.get("overview", "")
        questions = roadmap.get("research_questions", [])

        if overview or questions:
            st.markdown("---")
            col_ov, col_q = st.columns([0.52, 0.48])
            with col_ov:
                if overview:
                    st.markdown("**💡 Hướng tiếp cận & Phương pháp trọng tâm:**")
                    st.markdown(
                        f"""
                        <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 12px 14px; color: #cbd5e1; font-size: 0.9rem; line-height: 1.6;">
                            {overview}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            with col_q:
                if questions:
                    st.markdown("**❓ Câu hỏi nghiên cứu then chốt cần giải quyết:**")
                    q_items = "".join([f"<li style='margin-bottom: 4px;'>{q}</li>" for q in questions])
                    st.markdown(
                        f"""
                        <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px; padding: 12px 14px; color: #93c5fd; font-size: 0.88rem; line-height: 1.55;">
                            <ul style="margin: 0; padding-left: 18px;">{q_items}</ul>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    # 3. SƠ ĐỒ ĐỀ XUẤT CÁC BƯỚC NGHIÊN CỨU (MERMAID DIAGRAM)
    st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)
    st.markdown("#### 🔄 Sơ đồ quy trình các bước nghiên cứu")

    mermaid_code = roadmap.get("mermaid_code", "")
    if mermaid_code:
        with st.container(border=True):
            _render_mermaid_diagram(mermaid_code, height=360)
            with st.expander("📝 Xem mã nguồn sơ đồ Mermaid", expanded=False):
                st.code(mermaid_code, language="mermaid")
    else:
        st.info("Chưa có mã sơ đồ quy trình cho lộ trình này.")

    # 4. BẢNG ĐÁNH DẤU TIẾN TRÌNH CHI TIẾT (INTERACTIVE CHECKLIST)
    st.markdown("<div style='margin-top: 1.2rem;'></div>", unsafe_allow_html=True)
    col_head_tbl, col_act_tbl = st.columns([0.65, 0.35])
    with col_head_tbl:
        st.markdown("#### 📋 Bảng đánh dấu tiến trình thực hiện (Checklist)")
    with col_act_tbl:
        # Nút xuất kế hoạch ra file Markdown
        md_content = _export_roadmap_markdown(roadmap, store)
        st.download_button(
            label="📥 Xuất kế hoạch NCKH (.md)",
            data=md_content,
            file_name=f"ke_hoach_nghien_cuu_{store.topic[:20]}.md".replace(" ", "_"),
            mime="text/markdown",
            use_container_width=True,
        )

    phases = roadmap.get("phases", [])
    for p_idx, phase in enumerate(phases, 1):
        phase_name = phase.get("phase_name", f"Giai đoạn {p_idx}")
        phase_desc = phase.get("description", "")
        steps = phase.get("steps", [])

        # Tính tiến độ của riêng giai đoạn này
        p_total = len(steps)
        p_done = sum(1 for s in steps if store.get_step_progress(s.get("id", "")))
        p_pct = int((p_done / p_total) * 100) if p_total > 0 else 0

        # Phase Card Header
        status_color = "#10b981" if p_pct == 100 else ("#38bdf8" if p_pct > 0 else "#64748b")
        status_text = "Hoàn tất" if p_pct == 100 else f"{p_done}/{p_total} bước"

        with st.expander(f"🔹 {phase_name} ({status_text} - {p_pct}%)", expanded=(p_pct < 100)):
            if phase_desc:
                st.caption(f"🎯 *Mục tiêu giai đoạn:* {phase_desc}")

            # Danh sách từng bước trong giai đoạn
            for s_idx, step in enumerate(steps, 1):
                sid = step.get("id") or f"step_{p_idx}_{s_idx}"
                title = step.get("title", f"Bước {s_idx}")
                tasks = step.get("tasks", "")
                deliverable = step.get("deliverable", "")
                tools = step.get("tools_tips", "")
                is_done = store.get_step_progress(sid)

                # Dòng hiển thị bước với khung bo cong tinh tế
                with st.container(border=True):
                    col_chk, col_content, col_status = st.columns([0.08, 0.72, 0.20])

                    with col_chk:
                        # Canh lề trên để checkbox vừa vặn với tiêu đề
                        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                        new_checked = st.checkbox(
                            "",
                            value=is_done,
                            key=f"chk_step_{sid}",
                            label_visibility="collapsed",
                        )
                        if new_checked != is_done:
                            store.set_step_progress(sid, new_checked)
                            st.rerun()

                    with col_content:
                        # Hiệu ứng gạch ngang nhẹ nếu đã hoàn thành
                        title_style = (
                            "text-decoration: line-through; color: #64748b;"
                            if is_done
                            else "color: #f1f5f9; font-weight: 600;"
                        )
                        st.markdown(
                            f"<div style='font-size: 1rem; {title_style} margin-bottom: 4px;'>{title}</div>",
                            unsafe_allow_html=True,
                        )

                        if tasks:
                            st.markdown(
                                f"<div style='font-size: 0.86rem; color: #94a3b8; line-height: 1.5; margin-bottom: 6px;'><strong>Nhiệm vụ:</strong> {tasks}</div>",
                                unsafe_allow_html=True,
                            )

                        meta_row = []
                        if deliverable:
                            meta_row.append(f"<span style='color: #38bdf8;'>📦 <strong>Đầu ra:</strong> {deliverable}</span>")
                        if tools:
                            meta_row.append(f"<span style='color: #a5b4fc;'>🛠️ <strong>Công cụ:</strong> {tools}</span>")

                        if meta_row:
                            st.markdown(
                                f"<div style='font-size: 0.82rem; line-height: 1.5;'>{' &nbsp;•&nbsp; '.join(meta_row)}</div>",
                                unsafe_allow_html=True,
                            )

                    with col_status:
                        if is_done:
                            st.markdown(
                                """
                                <div style="display: flex; justify-content: flex-end; align-items: center; height: 100%;">
                                    <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); color: #34d399; font-size: 0.76rem; font-weight: 700; padding: 4px 10px; border-radius: 9999px;">
                                        ✓ Hoàn thành
                                    </span>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                """
                                <div style="display: flex; justify-content: flex-end; align-items: center; height: 100%;">
                                    <span style="background: rgba(100, 116, 139, 0.15); border: 1px solid rgba(100, 116, 139, 0.3); color: #94a3b8; font-size: 0.76rem; font-weight: 600; padding: 4px 10px; border-radius: 9999px;">
                                        ○ Chờ thực hiện
                                    </span>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
