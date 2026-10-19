"""
Cổng giao tiếp duy nhất với mô hình ngôn ngữ lớn (LLM), hỗ trợ cơ chế cache và quản lý hạn mức gọi.
Đầu vào: Prompt hoặc dữ liệu batch các bài báo cần phân tích.
Đầu ra: Chuỗi kết quả phản hồi chuẩn hóa hoặc định dạng cấu trúc từ mô hình AI.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Đảm bảo thư mục gốc dự án luôn có trong sys.path
_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from dotenv import load_dotenv
from google import genai
from google.genai import types

from config import settings
from utils.file_cache import cache_get, cache_set, make_key

load_dotenv()

# Quản lý thống kê mức độ sử dụng AI
_usage: dict[str, int] = {
    "calls": 0,
    "cache_hits": 0,
    "input_tokens": 0,
    "output_tokens": 0,
}

# Thời điểm gọi API thật gần nhất để kiểm soát giãn cách
_last_call_time: float = 0.0


def get_usage() -> dict[str, int]:
    """
    Lấy thông tin thống kê sử dụng AI trong phiên hiện tại.

    Đầu ra:
        dict gồm số lần gọi thật (calls), số lần trúng cache (cache_hits),
        tổng token vào (input_tokens) và tổng token ra (output_tokens).
    """
    return dict(_usage)


def reset_usage() -> None:
    """Đặt lại toàn bộ thông số sử dụng AI về 0."""
    _usage["calls"] = 0
    _usage["cache_hits"] = 0
    _usage["input_tokens"] = 0
    _usage["output_tokens"] = 0


def _get_api_key() -> str:
    """Lấy API key từ biến môi trường mà không in ra log."""
    key = os.getenv("AI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "Thiếu API key cho mô hình AI. Vui lòng thiết lập AI_API_KEY trong file .env."
        )
    return key


def _get_client() -> genai.Client:
    """Khởi tạo Client chính thức của google-genai."""
    api_key = _get_api_key()
    return genai.Client(api_key=api_key)


def _enforce_rate_limit() -> None:
    """Đảm bảo khoảng cách tối thiểu giữa 2 lần gọi mạng thật."""
    global _last_call_time
    min_interval = float(getattr(settings, "AI_MIN_INTERVAL_SEC", 4))
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)


def _update_last_call_time() -> None:
    """Cập nhật mốc thời gian sau khi kết thúc cuộc gọi thật."""
    global _last_call_time
    _last_call_time = time.time()


def _is_rate_limit_error(err: Exception) -> bool:
    """Kiểm tra xem lỗi có phải do giới hạn tốc độ (429) hoặc hết hạn mức (ResourceExhausted) hay không."""
    code = getattr(err, "code", None)
    if code == 429:
        return True
    msg = str(err).upper()
    return any(keyword in msg for keyword in ("429", "RESOURCE_EXHAUSTED", "RATE_LIMIT", "QUOTA"))


def _is_model_not_found_or_forbidden(err: Exception) -> bool:
    """Kiểm tra lỗi model không tồn tại hoặc không được phép (404/403)."""
    code = getattr(err, "code", None)
    if code in (404, 403):
        return True
    msg = str(err).upper()
    return any(
        keyword in msg
        for keyword in (
            "404",
            "403",
            "NOT_FOUND",
            "NOT FOUND",
            "PERMISSION_DENIED",
            "NOT SUPPORTED",
            "IS NOT FOUND",
        )
    )


def _is_network_error(err: Exception) -> bool:
    """Kiểm tra xem lỗi có phải do mất mạng hoặc timeout hay không."""
    msg = str(err).lower()
    return any(
        keyword in msg
        for keyword in ("connection", "timeout", "timed out", "unreachable", "name resolution")
    )


def _get_retry_delay(err: Exception, attempt: int) -> float:
    """Xác định thời gian chờ trước khi thử lại khi gặp lỗi 429."""
    msg = str(err)
    match = re.search(
        r"retry(?:\s+after|\s+in)?\s+([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|seconds)?",
        msg,
        re.IGNORECASE,
    )
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    # Mặc định chờ 5s cho lần thử lại thứ nhất, 15s cho lần thử lại thứ hai
    return 5.0 if attempt == 0 else 15.0


def _build_config(
    system: str = "",
    max_output_tokens: int = 1024,
    response_mime_type: Optional[str] = None,
) -> types.GenerateContentConfig:
    """Xây dựng cấu hình gọi mô hình Gemini bao gồm nhiệt độ và mức suy luận tiết kiệm token."""
    temperature = float(getattr(settings, "AI_TEMPERATURE", 0.2))

    config_kwargs: dict[str, Any] = {
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
    }
    if system:
        config_kwargs["system_instruction"] = system
    if response_mime_type:
        config_kwargs["response_mime_type"] = response_mime_type

    # Cố gắng đặt thinking_level='low' hoặc thinking_budget=0 để tiết kiệm token nếu SDK hỗ trợ
    try:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
    except Exception:
        try:
            config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        except Exception:
            pass

    try:
        return types.GenerateContentConfig(**config_kwargs)
    except Exception:
        # Bỏ qua thinking_config nếu phiên bản SDK từ chối
        config_kwargs.pop("thinking_config", None)
        return types.GenerateContentConfig(**config_kwargs)


def _extract_json_text(text: str) -> str:
    """Tự động bóc tách chuỗi JSON khi AI bọc trong khối code markdown ```json ... ```."""
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.split("\n")
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            clean = "\n".join(lines[1:-1]).strip()
        elif "```" in clean[3:]:
            parts = clean.split("```")
            if len(parts) >= 2:
                candidate = parts[1]
                if candidate.startswith("json"):
                    candidate = candidate[4:]
                clean = candidate.strip()
        else:
            first_newline = clean.find("\n")
            if first_newline != -1:
                clean = clean[first_newline + 1:].strip()
    return clean


def _try_repair_truncated_json(text: str) -> Optional[Any]:
    """Cố gắng khôi phục mảng JSON bị cắt ngang ở cuối do chạm giới hạn token."""
    clean = _extract_json_text(text)
    if clean.startswith("["):
        last_brace = clean.rfind("}")
        if last_brace != -1:
            candidate = clean[:last_brace + 1].strip() + "\n]"
            try:
                data = json.loads(candidate)
                if isinstance(data, list) and len(data) > 0:
                    return data
            except Exception:
                pass
    return None


def _execute_gemini_call(
    prompt: str,
    system: str,
    max_output_tokens: int,
    response_mime_type: Optional[str] = None,
) -> str:
    """
    Thực hiện gọi API Gemini với đầy đủ cơ chế giãn cách, retry 429 và fallback model.
    """
    client = _get_client()
    primary_model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-flash-latest")

    current_model = primary_model
    max_429_retries = 2
    attempt_429 = 0
    switched_to_fallback = False

    while True:
        _enforce_rate_limit()

        config = _build_config(
            system=system,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )

        try:
            response = client.models.generate_content(
                model=current_model,
                contents=prompt,
                config=config,
            )
            _update_last_call_time()

            # Ghi nhận số lượng token sử dụng
            _usage["calls"] += 1
            usage_meta = getattr(response, "usage_metadata", None)
            if usage_meta:
                _usage["input_tokens"] += int(getattr(usage_meta, "prompt_token_count", 0) or 0)
                _usage["output_tokens"] += int(getattr(usage_meta, "candidates_token_count", 0) or 0)

            return str(getattr(response, "text", "") or "")

        except Exception as e:
            _update_last_call_time()

            # Xử lý lỗi 429 (Hạn mức gọi)
            if _is_rate_limit_error(e):
                if attempt_429 < max_429_retries:
                    delay = _get_retry_delay(e, attempt_429)
                    attempt_429 += 1
                    time.sleep(delay)
                    continue
                if not switched_to_fallback and fallback_model and fallback_model != current_model:
                    current_model = fallback_model
                    switched_to_fallback = True
                    attempt_429 = 0
                    continue
                raise RuntimeError(
                    "Đã vượt quá hạn mức sử dụng API của AI (Lỗi 429 / Quota Exceeded)."
                ) from e

            # Xử lý lỗi model chính không tồn tại hoặc không được phép -> Thử sang model dự phòng
            if _is_model_not_found_or_forbidden(e):
                if not switched_to_fallback and fallback_model and fallback_model != current_model:
                    current_model = fallback_model
                    switched_to_fallback = True
                    continue
                raise RuntimeError(
                    f"Mô hình AI '{current_model}' không tồn tại hoặc không có quyền truy cập."
                ) from e

            # Xử lý lỗi mạng
            if _is_network_error(e):
                raise ConnectionError(
                    "Không thể kết nối đến máy chủ AI (Lỗi kết nối mạng hoặc timeout)."
                ) from e

            # Các lỗi khác
            raise RuntimeError(f"Lỗi khi gọi mô hình AI: {e}") from e


def call_llm(
    prompt: str,
    system: str = "",
    max_output_tokens: int = 1024,
    use_cache: bool = True,
) -> str:
    """
    Gọi mô hình ngôn ngữ lớn để sinh phản hồi dạng văn bản thường.

    Đầu vào:
        prompt: Câu lệnh hoặc nội dung cần phân tích.
        system: Lời nhắc hệ thống (system prompt).
        max_output_tokens: Số lượng token tối đa của phản hồi.
        use_cache: Bật/tắt lưu và đọc từ bộ nhớ đệm.

    Đầu ra:
        Chuỗi văn bản kết quả từ mô hình AI.
    """
    primary_model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    cache_key = make_key(primary_model, system, prompt)
    ttl_days = int(getattr(settings, "AI_CACHE_TTL_DAYS", 30))
    ttl_seconds = ttl_days * 86400

    if use_cache:
        cached_result = cache_get("ai", cache_key, ttl_seconds=ttl_seconds)
        if cached_result is not None:
            _usage["cache_hits"] += 1
            return str(cached_result)

    result_text = _execute_gemini_call(
        prompt=prompt,
        system=system,
        max_output_tokens=max_output_tokens,
        response_mime_type=None,
    )

    if use_cache:
        cache_set("ai", cache_key, result_text)

    return result_text


def call_llm_json(
    prompt: str,
    system: str = "",
    max_output_tokens: int = 2048,
    use_cache: bool = True,
) -> Any:
    """
    Gọi mô hình ngôn ngữ lớn ở chế độ trả về cấu trúc JSON (tự động bóc tách và thử lại nếu lỗi cú pháp).

    Đầu vào:
        prompt: Câu lệnh yêu cầu trả về JSON.
        system: Lời nhắc hệ thống.
        max_output_tokens: Giới hạn token đầu ra.
        use_cache: Bật/tắt cache.

    Đầu ra:
        Đối tượng Python (dict hoặc list) đã được parse từ JSON.
    """
    primary_model = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    cache_key = make_key(primary_model, system, prompt, "json")
    ttl_days = int(getattr(settings, "AI_CACHE_TTL_DAYS", 30))
    ttl_seconds = ttl_days * 86400

    if use_cache:
        cached_result = cache_get("ai", cache_key, ttl_seconds=ttl_seconds)
        if cached_result is not None:
            _usage["cache_hits"] += 1
            return cached_result

    # Gọi lần 1
    raw_response = _execute_gemini_call(
        prompt=prompt,
        system=system,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json",
    )
    clean_text = _extract_json_text(raw_response)

    try:
        parsed_data = json.loads(clean_text)
    except json.JSONDecodeError:
        # Parse lỗi thì thử lại đúng 1 lần
        retry_prompt = f"{prompt}\n\nLƯU Ý: Phải trả về cú pháp JSON hợp lệ, không kèm văn bản giải thích thừa."
        raw_retry = _execute_gemini_call(
            prompt=retry_prompt,
            system=system,
            max_output_tokens=max_output_tokens,
            response_mime_type="application/json",
        )
        clean_retry = _extract_json_text(raw_retry)
        try:
            parsed_data = json.loads(clean_retry)
        except json.JSONDecodeError as err:
            repaired = _try_repair_truncated_json(clean_retry) or _try_repair_truncated_json(clean_text)
            if repaired is not None:
                parsed_data = repaired
            else:
                raise ValueError(
                    f"Phản hồi từ AI không đúng định dạng JSON hợp lệ: {raw_retry[:200]}"
                ) from err

    if use_cache:
        cache_set("ai", cache_key, parsed_data)

    return parsed_data


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("Bắt đầu thử nghiệm gọi AI (call_llm)...")
    try:
        response_text = call_llm("Trả lời một câu ngắn: xin chào", use_cache=False)
        print("Kết quả:", response_text)
        print("Thống kê sử dụng (usage):", get_usage())
    except Exception as exc:
        print("Lỗi khi chạy thử nghiệm:", exc)
        print("Thống kê sử dụng (usage):", get_usage())
