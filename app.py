"""
Research Finder - Ứng dụng Streamlit tìm kiếm và tổng hợp tài liệu nghiên cứu kinh tế.
Giao diện kết nối trực tiếp với pipeline, ui, selection và export; không chứa logic nghiệp vụ.
"""

from __future__ import annotations

import hashlib
import importlib
from typing import Any

import streamlit as st

from config.settings import DEFAULT_YEAR_FROM
from export.excel_writer import papers_to_excel_bytes
from pipeline.search_pipeline import analyze_single, load_more, run_first_search

import selection.state
importlib.reload(selection.state)
from selection.state import SelectionStore, get_store

import ui.roadmap_page
importlib.reload(ui.roadmap_page)
from ui.roadmap_page import render_roadmap_page

from ui.load_more import render_load_more
from ui.paper_card import render_paper_card


def _get_safe_key(paper_id: str) -> str:
    """Tạo key duy nhất và an toàn cho Streamlit widget."""
    clean_id = str(paper_id or "").strip()
    if not clean_id:
        return "empty_id"
    return hashlib.md5(clean_id.encode("utf-8")).hexdigest()[:16]


# Cấu hình giao diện Streamlit (layout rộng, ẩn sidebar)
st.set_page_config(
    page_title="Nguyễn Huy Hoàng Lân Project - Research Finder",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS tinh chỉnh toàn diện giao diện: Ambient Glow Motion, Glassmorphism, Micro-animations & High-End Design
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* Nền Ambient Mesh với chuyển động ánh sáng mượt mà & lưới hạt tinh xảo */
    .stApp {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        background-color: #080c14 !important;
        background-image: 
            radial-gradient(circle at 18% 12%, rgba(59, 130, 246, 0.16) 0%, transparent 45%),
            radial-gradient(circle at 82% 22%, rgba(139, 92, 246, 0.14) 0%, transparent 40%),
            radial-gradient(circle at 50% 85%, rgba(14, 165, 233, 0.10) 0%, transparent 50%),
            radial-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px) !important;
        background-size: 100% 100%, 100% 100%, 100% 100%, 28px 28px !important;
        background-attachment: fixed !important;
        animation: ambientBreath 20s ease-in-out infinite alternate;
    }

    @keyframes ambientBreath {
        0% {
            background-position: 0% 0%, 0% 0%, 0% 0%, 0 0;
        }
        50% {
            background-position: 2% 4%, -2% -3%, 3% 2%, 0 0;
        }
        100% {
            background-position: -2% -3%, 3% 4%, -1% -2%, 0 0;
        }
    }

    /* Bảo vệ font của Material Symbols để không bị biến thành chữ thô */
    [data-testid="stIconMaterial"],
    .material-symbols-rounded,
    .material-symbols-outlined,
    .material-icons,
    [data-testid="stIconMaterial"] * {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
        font-weight: normal !important;
        font-style: normal !important;
    }

    /* Ẩn nút Deploy ở góc phải bên trên */
    .stDeployButton,
    [data-testid="stDeployButton"] {
        display: none !important;
    }
    header [data-testid="stToolbar"] {
        right: 1rem;
    }

    /* Tối ưu khoảng cách đỉnh trang - an toàn, không đè toolbar */
    header[data-testid="stHeader"] {
        height: 2.2rem !important;
        background: transparent !important;
    }
    .block-container,
    [data-testid="stMainBlockContainer"],
    .main .block-container {
        padding-top: 1.6rem !important;
        padding-bottom: 2.8rem !important;
        max-width: 1440px;
    }

    /* Banner thương hiệu phong cách Glassmorphic với viền phát sáng lướt qua */
    .rf-banner {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.92) 0%, rgba(26, 35, 58, 0.85) 50%, rgba(15, 23, 42, 0.92) 100%);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 18px;
        padding: 1.25rem 1.75rem;
        margin-bottom: 1.35rem;
        color: #ffffff;
        box-shadow: 0 10px 36px rgba(0, 0, 0, 0.45);
        position: relative;
        overflow: hidden;
    }
    .rf-banner::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent 0%, #38bdf8 25%, #818cf8 50%, #c084fc 75%, transparent 100%);
        animation: bannerShimmer 5s ease-in-out infinite;
    }
    @keyframes bannerShimmer {
        0% { opacity: 0.3; transform: translateX(-40%); }
        50% { opacity: 1; transform: translateX(40%); }
        100% { opacity: 0.3; transform: translateX(-40%); }
    }
    .rf-banner-inner {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 18px;
    }
    .rf-creator-credit {
        font-size: 0.88rem;
        color: #94a3b8;
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.12);
        padding: 6px 14px;
        border-radius: 10px;
        backdrop-filter: blur(8px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    .rf-creator-credit strong {
        color: #38bdf8;
        font-weight: 700;
    }
    .rf-banner-title {
        font-size: 2.15rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 14px;
        line-height: 1.25;
    }
    .rf-banner-pill {
        background: rgba(59, 130, 246, 0.22);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.45);
        font-size: 0.82rem;
        font-weight: 700;
        padding: 4px 13px;
        border-radius: 9999px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        animation: pulsePill 3s ease-in-out infinite;
    }
    @keyframes pulsePill {
        0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
        50% { box-shadow: 0 0 14px 3px rgba(59, 130, 246, 0.45); }
    }
    .rf-banner-desc {
        color: #cbd5e1;
        font-size: 1.05rem;
        margin-top: 8px;
        line-height: 1.6;
        font-weight: 450;
    }

    /* Glassmorphic Cards với hiệu ứng Fade-In & Hover Elevation đa tầng */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(145deg, rgba(15, 23, 42, 0.75) 0%, rgba(20, 29, 50, 0.65) 100%) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border: 1px solid rgba(255, 255, 255, 0.09) !important;
        border-radius: 16px !important;
        box-shadow: 0 4px 24px -2px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
        transition: all 0.32s cubic-bezier(0.16, 1, 0.3, 1) !important;
        animation: cardEntrance 0.42s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: rgba(99, 102, 241, 0.48) !important;
        box-shadow: 
            0 16px 36px -8px rgba(0, 0, 0, 0.6),
            0 0 24px -2px rgba(99, 102, 241, 0.22),
            inset 0 1px 0 rgba(255, 255, 255, 0.12) !important;
        transform: translateY(-3px);
    }
    @keyframes cardEntrance {
        from {
            opacity: 0;
            transform: translateY(12px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* Link tiêu đề bài báo phát sáng khi hover */
    .rf-paper-title-link {
        color: #60a5fa !important;
        text-decoration: none !important;
        font-weight: 700 !important;
        transition: color 0.2s ease, text-shadow 0.2s ease !important;
        display: inline-block;
        line-height: 1.45;
    }
    .rf-paper-title-link:hover {
        color: #93c5fd !important;
        text-shadow: 0 0 12px rgba(96, 165, 250, 0.5) !important;
    }
    .rf-paper-title-text {
        color: #f8fafc !important;
        font-weight: 700 !important;
        line-height: 1.45;
    }

    /* Badges & Chips hiện đại, sắc nét */
    .rf-badge-row {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        margin-bottom: 0.35rem;
    }
    .rf-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 3px 10px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        line-height: 1.4;
        transition: all 0.2s ease;
    }
    .rf-badge:hover {
        transform: translateY(-1px);
    }
    .rf-badge-idx {
        background: rgba(14, 165, 233, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(14, 165, 233, 0.35);
    }
    .rf-badge-year {
        background: rgba(148, 163, 184, 0.12);
        color: #e2e8f0;
        border: 1px solid rgba(148, 163, 184, 0.25);
    }
    .rf-badge-oa {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.35);
        text-decoration: none !important;
    }
    .rf-badge-oa:hover {
        background: rgba(16, 185, 129, 0.25);
        color: #6ee7b7;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.35);
    }
    .rf-badge-cite {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }
    .rf-badge-score {
        background: rgba(99, 102, 241, 0.18);
        color: #a5b4fc;
        border: 1px solid rgba(99, 102, 241, 0.38);
        box-shadow: 0 0 8px rgba(99, 102, 241, 0.15);
    }

    /* Meta tác giả & tạp chí */
    .rf-meta-row {
        color: #94a3b8;
        font-size: 0.88rem;
        margin: 0.25rem 0 0.55rem 0;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
    }
    .rf-meta-item {
        display: inline-flex;
        align-items: center;
    }
    .rf-meta-venue {
        color: #cbd5e1;
    }
    .rf-meta-doi {
        font-family: monospace;
        font-size: 0.8rem;
        background: rgba(255, 255, 255, 0.06);
        padding: 1px 6px;
        border-radius: 4px;
        color: #94a3b8;
    }

    /* AI Summary Box phong cách cao cấp */
    .rf-ai-box {
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.45) 0%, rgba(15, 23, 42, 0.65) 100%);
        border: 1px solid rgba(129, 140, 248, 0.28);
        border-left: 4px solid #6366f1;
        border-radius: 12px;
        padding: 0.85rem 1.15rem;
        margin: 0.65rem 0;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.3);
        transition: all 0.25s ease;
    }
    .rf-ai-box:hover {
        border-color: rgba(129, 140, 248, 0.45);
        box-shadow: 0 6px 22px rgba(99, 102, 241, 0.18);
    }
    .rf-ai-header {
        display: flex;
        align-items: center;
        gap: 7px;
        font-size: 0.82rem;
        font-weight: 700;
        color: #a5b4fc;
        margin-bottom: 0.35rem;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .rf-ai-text {
        color: #e2e8f0;
        font-size: 0.92rem;
        line-height: 1.6;
    }

    /* Khung Hạn chế nghiên cứu chuẩn học thuật */
    .rf-limitation-box {
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.28);
        border-left: 4px solid #f59e0b;
        border-radius: 10px;
        padding: 0.65rem 1rem;
        margin: 0.5rem 0 0.65rem 0;
        display: flex;
        align-items: flex-start;
        gap: 8px;
        font-size: 0.88rem;
        line-height: 1.55;
        transition: all 0.25s ease;
    }
    .rf-limitation-box:hover {
        background: rgba(245, 158, 11, 0.12);
        border-color: rgba(245, 158, 11, 0.45);
    }
    .rf-limitation-label {
        font-weight: 700;
        color: #fbbf24;
        white-space: nowrap;
    }
    .rf-limitation-val {
        color: #fde68a;
    }

    /* Abstract preview khi chưa tóm tắt AI */
    .rf-abstract-preview {
        background: rgba(255, 255, 255, 0.03);
        border-left: 3px solid rgba(255, 255, 255, 0.2);
        padding: 0.65rem 0.95rem;
        border-radius: 0 8px 8px 0;
        font-size: 0.88rem;
        color: #cbd5e1;
        line-height: 1.55;
    }
    .rf-abs-label {
        font-weight: 600;
        color: #f8fafc;
    }
    .rf-abs-pending {
        color: #f59e0b;
        font-size: 0.8rem;
        font-style: italic;
    }

    /* Keyword Pills & Topic Card */
    .rf-topic-card {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 0.75rem 1rem;
    }
    .rf-topic-label {
        color: #94a3b8;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 2px;
    }
    .rf-topic-val {
        color: #38bdf8;
        font-weight: 700;
        font-size: 1.05rem;
    }
    .rf-topic-sub {
        color: #64748b;
        font-size: 0.8rem;
        margin-top: 4px;
    }

    .rf-kw-box {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 0.75rem 1rem;
    }
    .rf-kw-title {
        color: #94a3b8;
        font-size: 0.82rem;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .rf-kw-list {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }
    .rf-kw-badge {
        display: inline-flex;
        align-items: center;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 6px;
        padding: 2px 8px;
        font-size: 0.8rem;
        color: #cbd5e1;
        transition: all 0.2s ease;
    }
    .rf-kw-badge:hover {
        background: rgba(255, 255, 255, 0.12);
        color: #ffffff;
        transform: translateY(-1px);
    }
    .rf-kw-primary {
        background: rgba(99, 102, 241, 0.2);
        border-color: rgba(99, 102, 241, 0.45);
        color: #c7d2fe;
        font-weight: 600;
    }

    /* Radar Pulse Indicator cho HUD tiến trình */
    .rf-progress-title {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 1.02rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 0.5rem;
    }
    .rf-pulse-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #38bdf8;
        box-shadow: 0 0 10px #38bdf8;
        animation: pulseRadar 1.6s infinite;
        flex-shrink: 0;
    }
    @keyframes pulseRadar {
        0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7); }
        70% { transform: scale(1.15); box-shadow: 0 0 0 9px rgba(56, 189, 248, 0); }
        100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
    }

    /* Inputs bo góc & viền phát sáng khi focus */
    .stTextInput input,
    .stNumberInput input {
        background: rgba(15, 23, 42, 0.55) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
        color: #f8fafc !important;
        font-size: 0.94rem !important;
        transition: all 0.24s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    .stTextInput input:hover,
    .stNumberInput input:hover {
        border-color: rgba(255, 255, 255, 0.22) !important;
    }
    .stTextInput input:focus,
    .stNumberInput input:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25), 0 0 16px rgba(99, 102, 241, 0.2) !important;
        background: rgba(15, 23, 42, 0.85) !important;
    }

    :root {
        --primary-color: #2563eb !important;
    }

    /* Buttons với Motion & Hiệu ứng tương tác mượt mà - Nút Tìm bài màu Xanh Blue chuẩn đẹp */
    button[kind="primary"],
    .stButton > button[type="primary"],
    .stButton > button[kind="primary"],
    button[data-testid="baseButton-primary"],
    button[data-testid="stBaseButton-primary"],
    button[data-testid*="primary"],
    div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[data-testid="stFormSubmitButton"] button[data-testid*="primary"],
    .stFormSubmitButton button[kind="primary"],
    .stFormSubmitButton button[data-testid*="primary"] {
        background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 50%, #3b82f6 100%) !important;
        background-color: #2563eb !important;
        background-size: 200% auto !important;
        border: 1px solid rgba(255, 255, 255, 0.22) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        color: #ffffff !important;
        box-shadow: 0 4px 18px rgba(37, 99, 235, 0.45) !important;
        transition: all 0.24s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    button[kind="primary"]:hover,
    .stButton > button[type="primary"]:hover,
    .stButton > button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover,
    button[data-testid*="primary"]:hover,
    div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[data-testid="stFormSubmitButton"] button[data-testid*="primary"]:hover,
    .stFormSubmitButton button[kind="primary"]:hover,
    .stFormSubmitButton button[data-testid*="primary"]:hover {
        background: linear-gradient(135deg, #2563eb 0%, #3b82f6 50%, #60a5fa 100%) !important;
        background-color: #1d4ed8 !important;
        background-position: right center !important;
        transform: translateY(-2px) scale(1.01) !important;
        box-shadow: 0 8px 26px rgba(37, 99, 235, 0.6), 0 0 18px rgba(59, 130, 246, 0.5) !important;
        color: #ffffff !important;
    }
    button[kind="primary"]:active,
    .stButton > button[type="primary"]:active,
    .stButton > button[kind="primary"]:active,
    button[data-testid="baseButton-primary"]:active,
    button[data-testid="stBaseButton-primary"]:active,
    button[data-testid*="primary"]:active,
    div[data-testid="stFormSubmitButton"] button[kind="primary"]:active,
    div[data-testid="stFormSubmitButton"] button[data-testid*="primary"]:active,
    .stFormSubmitButton button[kind="primary"]:active,
    .stFormSubmitButton button[data-testid*="primary"]:active {
        transform: translateY(1px) scale(0.98) !important;
    }

    button[kind="secondary"],
    .stButton > button[type="secondary"],
    button[data-testid="baseButton-secondary"] {
        background: rgba(255, 255, 255, 0.05) !important;
        backdrop-filter: blur(8px) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        color: #e2e8f0 !important;
        transition: all 0.22s ease !important;
    }
    button[kind="secondary"]:hover,
    .stButton > button[type="secondary"]:hover,
    button[data-testid="baseButton-secondary"]:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        border-color: rgba(59, 130, 246, 0.45) !important;
        color: #93c5fd !important;
        transform: translateY(-1.5px) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3) !important;
    }

    /* Checkbox tùy biến mượt mà */
    [data-testid="stCheckbox"] label {
        cursor: pointer !important;
        transition: color 0.2s ease !important;
    }
    [data-testid="stCheckbox"] label:hover {
        color: #a5b4fc !important;
    }
    [data-testid="stCheckbox"] input[type="checkbox"] {
        accent-color: #6366f1 !important;
        cursor: pointer !important;
    }

    /* Thanh tiến trình gradient phát sáng với animation shimmer */
    div[role="progressbar"],
    [data-testid="stProgress"] div[role="progressbar"],
    .stProgress div[role="progressbar"] {
        background: linear-gradient(90deg, #38bdf8 0%, #6366f1 50%, #c084fc 100%) !important;
        background-size: 200% 100% !important;
        border-radius: 9999px !important;
        transition: width 0.3s ease-in-out !important;
        box-shadow: 0 0 16px rgba(99, 102, 241, 0.55) !important;
        animation: progressShimmer 2s linear infinite !important;
    }
    @keyframes progressShimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    div[data-testid="stProgress"] > div,
    .stProgress > div {
        background-color: rgba(255, 255, 255, 0.08) !important;
        border-radius: 9999px !important;
        height: 9px !important;
        overflow: hidden !important;
    }

    /* Expander hiện đại */
    [data-testid="stExpander"] {
        background: rgba(15, 23, 42, 0.45) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        transition: all 0.25s ease !important;
    }
    [data-testid="stExpander"]:hover {
        border-color: rgba(99, 102, 241, 0.35) !important;
    }

    /* Tinh chỉnh thanh cuộn tinh xảo */
    ::-webkit-scrollbar {
        width: 7px;
        height: 7px;
    }
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 9999px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(99, 102, 241, 0.45);
    }

    /* =========================================================================
       LUXURY WELCOME HERO & EMPTY STATE
       ========================================================================= */
    .rf-welcome-hero {
        position: relative;
        overflow: hidden;
        background: linear-gradient(145deg, rgba(15, 23, 42, 0.75) 0%, rgba(30, 27, 75, 0.45) 50%, rgba(15, 23, 42, 0.85) 100%);
        backdrop-filter: blur(24px) saturate(190%);
        -webkit-backdrop-filter: blur(24px) saturate(190%);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        padding: 2.2rem 2.4rem;
        margin: 1.2rem 0;
        box-shadow: 0 12px 40px -10px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.08);
        transition: all 0.3s ease;
    }
    .rf-welcome-top-glow {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent 0%, #38bdf8 25%, #6366f1 50%, #c084fc 75%, transparent 100%);
    }
    .rf-welcome-badge {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        background: rgba(99, 102, 241, 0.14);
        border: 1px solid rgba(129, 140, 248, 0.32);
        border-radius: 9999px;
        padding: 4px 14px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #a5b4fc;
        margin-bottom: 0.9rem;
        text-transform: uppercase;
    }
    .rf-welcome-sparkle {
        color: #38bdf8;
        font-size: 0.85rem;
    }
    .rf-welcome-heading {
        font-size: 1.45rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        background: linear-gradient(135deg, #ffffff 0%, #e2e8f0 60%, #93c5fd 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.02em;
    }
    .rf-welcome-desc {
        color: #94a3b8;
        font-size: 0.94rem;
        line-height: 1.65;
        max-width: 860px;
        margin: 0 0 1.6rem 0;
    }
    .rf-highlight-btn {
        color: #60a5fa;
        font-weight: 600;
        background: rgba(37, 99, 235, 0.18);
        padding: 2px 8px;
        border-radius: 6px;
        border: 1px solid rgba(59, 130, 246, 0.35);
    }
    .rf-feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 16px;
        margin-bottom: 1.5rem;
    }
    .rf-feature-card {
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.15rem 1.25rem;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .rf-feature-card:hover {
        border-color: rgba(99, 102, 241, 0.45);
        background: rgba(30, 41, 59, 0.55);
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    }
    .rf-feature-icon-wrapper {
        width: 38px;
        height: 38px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.15rem;
        margin-bottom: 0.75rem;
        border: 1px solid;
    }
    .rf-feature-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #f1f5f9;
        margin-bottom: 0.35rem;
    }
    .rf-feature-text {
        font-size: 0.84rem;
        color: #94a3b8;
        line-height: 1.55;
    }
    .rf-welcome-tip {
        display: flex;
        align-items: center;
        gap: 12px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px dashed rgba(255, 255, 255, 0.14);
        border-radius: 10px;
        padding: 0.75rem 1rem;
    }
    .rf-tip-badge {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid rgba(245, 158, 11, 0.35);
        color: #fbbf24;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 6px;
        white-space: nowrap;
    }
    .rf-tip-text {
        color: #cbd5e1;
        font-size: 0.86rem;
        line-height: 1.5;
    }

    /* Khung thông báo không tìm thấy kết quả sang trọng */
    .rf-empty-search-card {
        background: linear-gradient(145deg, rgba(15, 23, 42, 0.75) 0%, rgba(30, 27, 75, 0.35) 100%);
        border: 1px solid rgba(245, 158, 11, 0.28);
        border-left: 4px solid #f59e0b;
        border-radius: 14px;
        padding: 1.5rem 1.85rem;
        margin: 1.2rem 0;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    }
    .rf-empty-icon {
        font-size: 1.6rem;
        margin-bottom: 0.5rem;
    }
    .rf-empty-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 0.35rem;
    }
    .rf-empty-sub {
        font-size: 0.92rem;
        color: #94a3b8;
        margin-bottom: 0.85rem;
    }
    .rf-empty-topic {
        color: #38bdf8;
        font-weight: 600;
    }
    .rf-empty-hints {
        color: #cbd5e1;
        font-size: 0.88rem;
        line-height: 1.6;
    }
    .rf-empty-hints ul {
        margin: 0.35rem 0 0 1.2rem;
        padding: 0;
    }
    .rf-empty-hints li {
        margin-bottom: 0.2rem;
    }

    /* =========================================================================
       LUXURY TABS / TRANG MỤC ĐIỀU HƯỚNG HIỆN ĐẠI
       ========================================================================= */
    div[data-testid="stTabs"] {
        margin-top: 0.3rem;
        margin-bottom: 1.25rem;
    }
    div[data-testid="stTabs"] [role="tablist"] {
        gap: 10px;
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 6px;
        border-radius: 14px;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }
    div[data-testid="stTabs"] button[role="tab"] {
        border-radius: 10px !important;
        padding: 9px 20px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        color: #94a3b8 !important;
        border: none !important;
        background: transparent !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:hover {
        color: #f8fafc !important;
        background: rgba(255, 255, 255, 0.06) !important;
    }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: #ffffff !important;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.9) 0%, rgba(59, 130, 246, 0.75) 100%) !important;
        box-shadow: 0 4px 18px rgba(37, 99, 235, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.25) !important;
        border: 1px solid rgba(147, 197, 253, 0.4) !important;
    }
    div[data-testid="stTabs"] hr {
        display: none !important;
    }

    /* Banner Lộ trình NCKH */
    .rf-roadmap-banner {
        position: relative;
        overflow: hidden;
        background: linear-gradient(145deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 27, 75, 0.55) 50%, rgba(15, 23, 42, 0.85) 100%);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 16px;
        padding: 1.25rem 1.75rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 10px 32px rgba(0, 0, 0, 0.45);
    }
    .rf-roadmap-banner-glow {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent 0%, #38bdf8 30%, #818cf8 60%, #c084fc 80%, transparent 100%);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Banner thương hiệu hiện đại
st.markdown(
    """
    <div class="rf-banner">
        <div class="rf-banner-inner">
            <div>
                <div class="rf-banner-title">
                    <span>📚 Research Finder</span>
                    <span class="rf-banner-pill">AI Academic</span>
                </div>
                <div class="rf-banner-desc">
                    Hệ thống tìm kiếm, sàng lọc và trích xuất tài liệu nghiên cứu kinh tế học thuật thông minh
                </div>
            </div>
            <div class="rf-creator-credit">
                <span>Dự án của: <strong>Nguyễn Huy Hoàng Lân</strong></span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

def render_search_page(store: SelectionStore) -> None:
    """Render trang tìm kiếm, sàng lọc và trích xuất tài liệu nghiên cứu."""
    # =========================================================================
    # PHẦN TRÊN: KHUNG ĐỀ TÀI NGHIÊN CỨU & BỘ LỌC
    # =========================================================================
    with st.container(border=True):
        st.markdown("#### 🎯 Đề tài nghiên cứu")

        with st.form("search_form", border=False):
            # Hàng 1: Ô nhập đề tài & Nút Tìm bài (màu xanh blue nổi bật)
            col_topic, col_find = st.columns([0.85, 0.15])
            with col_topic:
                topic_input = st.text_input(
                    "Nhập đề tài nghiên cứu:",
                    value=store.topic,
                    placeholder="Ví dụ: fintech monetary policy, kinh tế xanh Việt Nam...",
                    label_visibility="collapsed",
                )
            with col_find:
                find_clicked = st.form_submit_button("🔎 Tìm bài", type="primary", use_container_width=True)

            # Hàng 2: Ô năm bắt đầu, Số bài tìm kiếm & Nút Đặt lại nằm ngang hàng
            col_yr, col_limit, col_spacer, col_reset = st.columns([0.22, 0.28, 0.35, 0.15])
            with col_yr:
                year_from = st.number_input(
                    "Năm bắt đầu:",
                    min_value=1900,
                    max_value=2030,
                    value=int(DEFAULT_YEAR_FROM),
                    step=1,
                    help="Giới hạn năm xuất bản bài báo học thuật cần tìm kiếm",
                )
            with col_limit:
                target_options = [5, 10, 15, 20]
                current_target = getattr(store, "target_count", 10)
                default_idx = target_options.index(current_target) if current_target in target_options else 1
                target_count = st.selectbox(
                    "Số bài tìm kiếm:",
                    options=target_options,
                    index=default_idx,
                    format_func=lambda x: f"{x} bài",
                    help="Chọn số lượng bài báo cần tìm kiếm và phân tích chuyên sâu (5, 10, 15 hoặc 20 bài)",
                )
            with col_reset:
                # Canh lề trên để nút Đặt lại nằm ngang bằng với ô điền số năm bắt đầu
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                reset_clicked = st.form_submit_button("🔄 Đặt lại", use_container_width=True)

        if reset_clicked:
            store.reset()
            for k in list(st.session_state.keys()):
                if "Nhập đề tài" in str(k):
                    st.session_state[k] = ""
            st.rerun()

        # Sau khi nhập đề tài: Hiển thị thông tin đề tài & từ khóa AI gợi ý
        if store.topic:
            st.markdown("---")
            col_topic_info, col_kw_info = st.columns([0.4, 0.6])
            with col_topic_info:
                st.markdown(
                    f"""
                    <div class="rf-topic-card">
                        <div class="rf-topic-label">📌 Đề tài đang tra cứu:</div>
                        <div class="rf-topic-val">{store.topic}</div>
                        <div class="rf-topic-sub">Kho ứng viên chờ xem thêm: <strong>{store.pool_size()} bài báo</strong></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col_kw_info:
                if store.keywords:
                    pri_en = store.keywords.get("primary_en", "")
                    extra_en = store.keywords.get("en", [])
                    extra_vi = store.keywords.get("vi", [])

                    kw_html: list[str] = []
                    if pri_en:
                        kw_html.append(f'<span class="rf-kw-badge rf-kw-primary">🏷️ {pri_en}</span>')
                    for k in extra_en[:3]:
                        kw_html.append(f'<span class="rf-kw-badge">🌐 {k}</span>')
                    for k in extra_vi[:2]:
                        kw_html.append(f'<span class="rf-kw-badge">🇻🇳 {k}</span>')

                    if kw_html:
                        st.markdown(
                            f"""
                            <div class="rf-kw-box">
                                <div class="rf-kw-title">Gợi ý từ khóa AI đa chiều:</div>
                                <div class="rf-kw-list">{" ".join(kw_html)}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # =========================================================================
    # PHẦN DƯỚI: KẾT QUẢ NGHIÊN CỨU (FULL WIDTH)
    # =========================================================================
    st.subheader("📄 Kết quả nghiên cứu")

    # Xử lý khi bấm nút "Tìm bài"
    if find_clicked:
        cleaned_topic = topic_input.strip()
        if cleaned_topic:
            import threading
            import time

            # Khung thanh tiến trình tìm kiếm hiển thị cố định, rõ ràng với radar pulse animation
            status_box = st.container(border=True)
            with status_box:
                st.markdown(
                    """
                    <div class="rf-progress-title">
                        <div class="rf-pulse-dot"></div>
                        <span>Đang tìm kiếm & xử lý tài liệu học thuật</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                step_text = st.empty()
                progress_bar = st.progress(0.0)

            state: dict[str, Any] = {
                "stage": "Phân tích đề tài & sinh từ khóa học thuật...",
                "results": None,
                "error": None,
                "done": False,
            }

            def progress_callback(pct: float, msg: str) -> None:
                state["stage"] = msg

            def worker_thread() -> None:
                try:
                    state["results"] = run_first_search(
                        cleaned_topic,
                        store,
                        year_from=int(year_from),
                        on_progress=progress_callback,
                        batch_size=int(target_count),
                    )
                except Exception as exc:
                    state["error"] = exc
                finally:
                    state["done"] = True

            thread = threading.Thread(target=worker_thread, daemon=True)
            thread.start()

            # Vòng lặp tăng tiến độ mượt mà, liên tục từ 0% tới ~92% trong khi chờ kết quả
            prog = 0.02
            while not state["done"]:
                time.sleep(0.05)
                # Tăng đều liên tục: mượt mà, không khựng, tiệm cận 92% nếu chờ lâu
                if prog < 0.25:
                    prog += 0.008
                elif prog < 0.60:
                    prog += 0.005
                elif prog < 0.85:
                    prog += 0.003
                else:
                    prog = min(0.92, prog + (0.93 - prog) * 0.03)

                pct_val = max(0.0, min(1.0, prog))
                pct_int = int(pct_val * 100)
                current_msg = state.get("stage", "Đang xử lý tài liệu...")
                step_text.markdown(f"**{current_msg}** (`{pct_int}%`)")
                progress_bar.progress(pct_val)

            thread.join(timeout=1.0)

            # Lướt đều, mượt mà từ vị trí hiện tại lên thẳng 100% khi xử lý xong
            while prog < 1.0:
                time.sleep(0.02)
                prog = min(1.0, prog + 0.03)
                pct_int = int(prog * 100)
                final_count = len(state["results"]) if state["results"] else 0
                step_text.markdown(f"**Hoàn tất! Đã tìm thấy {final_count} bài báo đầu tiên.** (`{pct_int}%`)")
                progress_bar.progress(prog)

            time.sleep(0.4)
            status_box.empty()

            if state["error"]:
                st.error(f"Lỗi AI trong quá trình xử lý: {state['error']}")
            elif not state["results"]:
                st.info("Không tìm thấy bài báo nào phù hợp với đề tài trên.")
            else:
                st.rerun()
        else:
            st.warning("Vui lòng nhập đề tài nghiên cứu ở khung phía trên trước khi bấm Tìm bài.")

    displayed_papers = store.get_all()
    selected_papers = store.get_selected()

    # Cảnh báo khi có bài chưa được tóm tắt bằng AI
    if displayed_papers:
        unanalyzed_with_abs = [
            p for p in displayed_papers
            if not getattr(p, "analyzed", False) and bool((p.abstract or "").strip())
        ]
        if unanalyzed_with_abs:
            st.warning(
                f"Có {len(unanalyzed_with_abs)} bài báo chưa được tóm tắt bằng AI (do hết hạn mức hoặc sai key). "
                "Các bài báo vẫn được hiển thị đầy đủ bên dưới. Bạn có thể bấm 'Tóm tắt bằng AI' ở từng bài để thử lại."
            )

        # Thanh tác vụ: Thống kê & Nút "Xuất Excel" chỉ xuất bài đã chọn
        col_summary, col_roadmap_tip, col_export = st.columns([0.48, 0.22, 0.30])

        with col_summary:
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; gap: 8px; height: 100%; padding: 6px 0;">
                    <span style="font-size: 0.95rem; color: #94a3b8;">
                        Đang hiển thị: <strong style="color: #f8fafc;">{len(displayed_papers)}</strong> bài &nbsp;•&nbsp; 
                        Đã chọn: <strong style="color: #38bdf8;">{len(selected_papers)}</strong> bài
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_roadmap_tip:
            st.markdown(
                """
                <div style="display: flex; align-items: center; justify-content: center; height: 100%;">
                    <span style="background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.35); color: #a5b4fc; font-size: 0.78rem; font-weight: 600; padding: 4px 10px; border-radius: 8px;">
                        🗺️ Tab trên: Lộ trình & Sơ đồ NCKH
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_export:
            if selected_papers:
                excel_bytes = papers_to_excel_bytes(selected_papers)
                st.download_button(
                    label=f"📥 Xuất Excel ({len(selected_papers)} bài đã chọn)",
                    data=excel_bytes,
                    file_name="tai_lieu_nghien_cuu.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )
            else:
                st.button(
                    "📥 Xuất Excel",
                    disabled=True,
                    use_container_width=True,
                    help="Vui lòng tích chọn ít nhất 1 bài báo để xuất Excel",
                )

        # Hiện các ô bằng ui.paper_card có đánh số thứ tự từng bài (Bài #1, #2, ...)
        for idx, paper in enumerate(displayed_papers, 1):
            render_paper_card(paper, store, index=idx)

        # Nút "Thêm 5 bài" (ui.load_more) → pipeline.load_more
        st.markdown("---")
        col_center = st.columns([0.35, 0.3, 0.35])[1]
        with col_center:
            if render_load_more():
                with st.spinner("Đang tải thêm bài tiếp theo..."):
                    try:
                        new_batch = load_more(store, year_from=int(year_from))
                        if new_batch:
                            st.success(f"Đã tải thêm {len(new_batch)} bài báo mới!")
                        else:
                            st.info("Không còn bài báo nào mới trong kho ứng viên hoặc nguồn tìm kiếm.")
                        st.rerun()
                    except Exception as exc:
                        st.warning(f"Lỗi khi tải thêm bài: {exc}")

    elif store.topic:
        st.markdown(
            f"""<div class="rf-empty-search-card">
<div class="rf-empty-icon">🔎</div>
<div class="rf-empty-title">Chưa tìm thấy bài báo phù hợp</div>
<div class="rf-empty-sub">Đề tài đang tra cứu: <span class="rf-empty-topic">{store.topic}</span></div>
<div class="rf-empty-hints">
<span>💡 <strong>Gợi ý cải thiện kết quả:</strong></span>
<ul>
<li>Rút gọn đề tài thành cụm từ khóa trọng tâm (ví dụ: <em>kinh tế số xuất khẩu nông sản</em>).</li>
<li>Giảm năm bắt đầu để mở rộng khoảng thời gian tìm kiếm.</li>
<li>Thử dùng các thuật ngữ học thuật tiếng Anh tương đương.</li>
<li>Chuyển sang tab <strong>🗺️ Đề xuất lộ trình & Bảng tiến trình</strong> để lập khung kế hoạch nghiên cứu trước.</li>
</ul>
</div>
</div>""",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """<div class="rf-welcome-hero">
<div class="rf-welcome-top-glow"></div>
<div class="rf-welcome-content">
<div class="rf-welcome-badge"><span class="rf-welcome-sparkle">✦</span><span>HỆ THỐNG TRA CỨU HỌC THUẬT & PHÂN TÍCH AI CHUYÊN SÂU</span></div>
<h3 class="rf-welcome-heading">Sẵn sàng khám phá & tổng quan tài liệu nghiên cứu</h3>
<p class="rf-welcome-desc">Nhập đề tài hoặc câu hỏi nghiên cứu vào ô bên trên và bấm nút <span class="rf-highlight-btn">🔎 Tìm bài</span>. Hệ thống sẽ tự động mở rộng từ khóa song ngữ, truy vấn kho dữ liệu học thuật mở toàn cầu <strong>OpenAlex</strong> (hơn 250M+ ấn phẩm), trích xuất phương pháp - kết quả và phân tích hạn chế của tài liệu đối với đề tài.</p>
<div class="rf-feature-grid">
<div class="rf-feature-card">
<div class="rf-feature-icon-wrapper" style="background: rgba(56, 189, 248, 0.12); border-color: rgba(56, 189, 248, 0.3); color: #38bdf8;">🌐</div>
<div class="rf-feature-title">Kho dữ liệu 250M+ bài báo</div>
<div class="rf-feature-text">Truy vấn dữ liệu học thuật toàn diện từ OpenAlex với đầy đủ tạp chí, tác giả, chỉ số trích dẫn và liên kết Open Access.</div>
</div>
<div class="rf-feature-card">
<div class="rf-feature-icon-wrapper" style="background: rgba(99, 102, 241, 0.14); border-color: rgba(99, 102, 241, 0.35); color: #a5b4fc;">🧠</div>
<div class="rf-feature-title">Phân tích & Chỉ rõ hạn chế</div>
<div class="rf-feature-text">Mô hình AI trích xuất phương pháp, kết quả chính và chỉ rõ hạn chế/khoảng trống của bài báo đối với đề tài cụ thể.</div>
</div>
<div class="rf-feature-card">
<div class="rf-feature-icon-wrapper" style="background: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.3); color: #34d399;">📊</div>
<div class="rf-feature-title">Xuất Excel 18 cột NCKH</div>
<div class="rf-feature-text">Lựa chọn các bài báo tâm đắc và xuất bảng tổng quan tài liệu chuẩn hóa 18 cột cho đề tài nghiên cứu khoa học.</div>
</div>
</div>
<div class="rf-welcome-tip">
<div class="rf-tip-badge">💡 MẸO NHỎ</div>
<div class="rf-tip-text">Bạn có thể chuyển giữa 2 trang mục ở tab phía trên: <strong>📚 Tìm kiếm tài liệu</strong> và <strong>🗺️ Đề xuất lộ trình & Bảng tiến trình</strong> để quản lý toàn diện đề tài NCKH.</div>
</div>
</div>
</div>""",
            unsafe_allow_html=True,
        )


# Lấy SelectionStore singleton
store = get_store()
if not hasattr(store, "roadmap") or store.roadmap is None:
    store.roadmap = {}
if not hasattr(store, "roadmap_progress") or store.roadmap_progress is None:
    store.roadmap_progress = {}

# Phân chia trang mục khoa học & hiện đại: Tab Tìm kiếm & Tab Đề xuất lộ trình NCKH
tab_search, tab_roadmap = st.tabs(
    [
        "📚 Tìm kiếm & Tổng hợp tài liệu",
        "🗺️ Đề xuất lộ trình & Bảng tiến trình",
    ]
)

with tab_search:
    render_search_page(store)

with tab_roadmap:
    render_roadmap_page(store)

