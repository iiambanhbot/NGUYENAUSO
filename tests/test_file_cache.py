"""
Unit tests cho utils/file_cache.py.
Kiểm tra make_key, cache_set, cache_get với thư mục tạm (tmp_path),
các kịch bản: ghi/đọc, hết hạn TTL, file hỏng, khóa không tồn tại.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from utils.file_cache import cache_get, cache_set, make_key


@pytest.fixture(autouse=True)
def setup_tmp_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Thiết lập thư mục cache tạm thời cho từng test case."""
    cache_dir = tmp_path / "test_cache"
    monkeypatch.setattr("config.settings.CACHE_DIR", str(cache_dir))
    return cache_dir


def test_make_key_consistency_and_format() -> None:
    """Kiểm tra make_key tạo ra chuỗi hex ngắn 16 ký tự và có tính tất định."""
    key1 = make_key("openalex", "kinh tế việt nam", "2020")
    key2 = make_key("openalex", "kinh tế việt nam", "2020")
    key3 = make_key("openalex", "kinh tế việt nam", "2021")

    assert isinstance(key1, str)
    assert len(key1) == 16
    assert key1 == key2
    assert key1 != key3


def test_cache_set_and_get_success(setup_tmp_cache: Path) -> None:
    """Kiểm tra ghi dữ liệu vào cache và đọc lại thành công."""
    namespace = "search"
    key = make_key("query_1")
    data = {
        "title": "Bài báo mẫu",
        "scores": [1, 2, 3],
        "is_active": True,
    }

    cache_set(namespace, key, data)

    # Đảm bảo file được tạo đúng đường dẫn
    target_file = setup_tmp_cache / namespace / f"{key}.json"
    assert target_file.is_file()

    # Đọc lại với TTL còn hạn
    result = cache_get(namespace, key, ttl_seconds=3600)
    assert result == data


def test_cache_get_missing_key() -> None:
    """Kiểm tra cache_get trả về None khi khóa không tồn tại."""
    result = cache_get("non_existent", "missing_key", ttl_seconds=3600)
    assert result is None


def test_cache_get_expired(setup_tmp_cache: Path) -> None:
    """Kiểm tra cache_get trả về None khi cache đã hết hạn TTL."""
    namespace = "openalex"
    key = make_key("query_expired")
    data = {"status": "ok"}

    cache_set(namespace, key, data)

    # Đọc với TTL = 0 giây ngay lập tức hết hạn
    result = cache_get(namespace, key, ttl_seconds=0)
    assert result is None


def test_cache_get_corrupted_json(setup_tmp_cache: Path) -> None:
    """Kiểm tra cache_get trả về None khi file cache bị lỗi định dạng JSON."""
    namespace = "corrupted_ns"
    key = "bad_file"
    folder = setup_tmp_cache / namespace
    folder.mkdir(parents=True, exist_ok=True)
    corrupted_file = folder / f"{key}.json"

    # Ghi nội dung JSON không hợp lệ
    with open(corrupted_file, "w", encoding="utf-8") as f:
        f.write("{ invalid json content: true, ")

    result = cache_get(namespace, key, ttl_seconds=3600)
    assert result is None


def test_cache_atomic_overwrite_and_no_leftover_tmp(setup_tmp_cache: Path) -> None:
    """Kiểm tra ghi đè an toàn và không để lại các file tạm sau khi ghi."""
    namespace = "atomic_ns"
    key = "key_atomic"

    cache_set(namespace, key, {"version": 1})
    assert cache_get(namespace, key, ttl_seconds=3600) == {"version": 1}

    # Ghi đè giá trị mới
    cache_set(namespace, key, {"version": 2})
    assert cache_get(namespace, key, ttl_seconds=3600) == {"version": 2}

    # Kiểm tra thư mục không còn sót file tạm *.tmp.*
    folder = setup_tmp_cache / namespace
    tmp_files = list(folder.glob("*.tmp.*"))
    assert len(tmp_files) == 0
