"""
Thành phần giao diện nút tải thêm bài báo trong ứng dụng Streamlit.
Đầu vào: Hằng số LOAD_MORE_SIZE từ config.settings.
Đầu ra: Trả về True khi người dùng click nút tải thêm bài.
"""

from __future__ import annotations

import streamlit as st

from config.settings import LOAD_MORE_SIZE


def render_load_more() -> bool:
    """
    Hiển thị nút 'Thêm {LOAD_MORE_SIZE} bài' và trả về True nếu được bấm.

    Đầu ra:
        bool: True khi người dùng click vào nút, ngược lại False.
    """
    return bool(
        st.button(
            f"➕ Thêm {LOAD_MORE_SIZE} bài",
            key="btn_load_more",
            type="secondary",
            use_container_width=True,
        )
    )
