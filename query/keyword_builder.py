"""
Chuyển đổi chủ đề nghiên cứu thành từ khóa song ngữ Việt/Anh để truy vấn tài liệu học thuật.
Đầu vào: Chủ đề nghiên cứu kinh tế do người dùng nhập (tiếng Việt hoặc tiếng Anh).
Đầu ra: Dictionary chứa từ khóa chính tiếng Anh, các từ khóa tiếng Anh bổ sung và từ khóa tiếng Việt.
"""

from __future__ import annotations

from typing import Any

from ai_analysis.llm_client import call_llm_json


def build_keywords(topic: str) -> dict[str, Any]:
    """
    Xây dựng tập từ khóa tìm kiếm học thuật song ngữ dựa trên đề tài nghiên cứu.
    Thực hiện đúng 1 lần gọi duy nhất tới call_llm_json (max_output_tokens=400).
    Nếu gặp lỗi, tự động chuyển về phương án dự phòng an toàn, không ném ngoại lệ.

    Đầu vào:
        topic: Đề tài hoặc chủ đề nghiên cứu kinh tế.

    Đầu ra:
        dict với cấu trúc:
        {
            "primary_en": str,       # Cụm tìm kiếm học thuật tiếng Anh 4-8 từ
            "en": list[str],          # 2-3 cụm từ khóa tiếng Anh bổ sung
            "vi": list[str]           # 2 cụm từ khóa tiếng Việt
        }
    """
    clean_topic = topic.strip()
    if not clean_topic:
        return {"primary_en": "", "en": [], "vi": []}

    fallback = {
        "primary_en": clean_topic,
        "en": [],
        "vi": [clean_topic],
    }

    system_prompt = (
        "You are an academic economic research specialist. "
        "Generate focused academic search queries strictly as JSON."
    )

    user_prompt = (
        f"Topic: {clean_topic}\n\n"
        "Generate academic search keywords as JSON with:\n"
        '- "primary_en": A concise academic English search phrase (4-8 words) closely matching the topic.\n'
        '- "en": A list of 2-3 additional academic English search phrases or synonyms.\n'
        '- "vi": A list of 2 Vietnamese search phrases.'
    )

    try:
        data = call_llm_json(
            prompt=user_prompt,
            system=system_prompt,
            max_output_tokens=400,
            use_cache=True,
        )

        if not isinstance(data, dict):
            return fallback

        primary_en = str(data.get("primary_en", "") or "").strip()
        if not primary_en:
            primary_en = clean_topic

        raw_en = data.get("en", [])
        en_list = [str(item).strip() for item in raw_en if str(item).strip()] if isinstance(raw_en, list) else []

        raw_vi = data.get("vi", [])
        vi_list = [str(item).strip() for item in raw_vi if str(item).strip()] if isinstance(raw_vi, list) else []

        return {
            "primary_en": primary_en,
            "en": en_list,
            "vi": vi_list if vi_list else [clean_topic],
        }

    except Exception:
        return fallback
