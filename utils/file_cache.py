"""
Cơ chế lưu trữ và truy xuất bộ nhớ tạm (cache) dạng JSON trên đĩa cứng có thời hạn sử dụng (TTL).
Đầu vào: Khóa định danh (cache key), dữ liệu JSON cần lưu và thời gian sống (TTL).
Đầu ra: Dữ liệu đã lưu trong cache nếu còn hạn, hoặc None nếu hết hạn/chưa tồn tại.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from config import settings


def make_key(*parts: str) -> str:
    """
    Tạo khóa định danh (cache key) bằng cách ghép các chuỗi và băm SHA-256.

    Đầu vào:
        *parts: Các chuỗi thành phần cần ghép lại.

    Đầu ra:
        Chuỗi hex băm ngắn 16 ký tự.
    """
    raw = ":".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _get_target_path(namespace: str, key: str) -> Path:
    """
    Xác định đường dẫn file cache JSON theo namespace và key.

    Đầu vào:
        namespace: Phân vùng cache (ví dụ: 'openalex', 'ai_screen').
        key: Khóa định danh file.

    Đầu ra:
        Đối tượng Path dẫn tới file {CACHE_DIR}/{namespace}/{key}.json.
    """
    base_dir = Path(settings.CACHE_DIR)
    return base_dir / namespace / f"{key}.json"


def cache_get(namespace: str, key: str, ttl_seconds: int) -> Optional[Any]:
    """
    Đọc dữ liệu từ file cache JSON tại cache/{namespace}/{key}.json.
    Nếu file không tồn tại, hết hạn TTL hoặc nội dung hỏng thì trả về None.

    Đầu vào:
        namespace: Phân vùng thư mục cache.
        key: Khóa định danh cache.
        ttl_seconds: Thời gian sống tối đa của cache (tính bằng giây).

    Đầu ra:
        Dữ liệu gốc đã lưu nếu hợp lệ, ngược lại trả về None.
    """
    target_path = _get_target_path(namespace, key)

    if not target_path.is_file():
        return None

    try:
        now = time.time()
        file_mtime = os.path.getmtime(target_path)
        if now - file_mtime > ttl_seconds:
            return None

        with open(target_path, "r", encoding="utf-8") as f:
            content = json.load(f)

        if isinstance(content, dict) and "_cached_at" in content and "_data" in content:
            cached_at = content["_cached_at"]
            if now - cached_at > ttl_seconds:
                return None
            return content["_data"]

        return content
    except Exception:
        return None


def cache_set(namespace: str, key: str, value: Any) -> None:
    """
    Ghi dữ liệu JSON vào cache, tự động tạo thư mục nếu chưa có.
    Ghi qua file tạm thời rồi đổi tên để đảm bảo tính nguyên tử (atomic write).

    Đầu vào:
        namespace: Phân vùng thư mục cache.
        key: Khóa định danh cache.
        value: Dữ liệu cần lưu trữ (phải serialize được sang JSON).
    """
    target_path = _get_target_path(namespace, key)
    target_dir = target_path.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    temp_path = target_dir / f"{key}.tmp.{uuid.uuid4().hex}"

    payload = {
        "_cached_at": time.time(),
        "_data": value,
    }

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        os.replace(temp_path, target_path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
