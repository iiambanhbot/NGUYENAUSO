"""
Unit tests cho ai_analysis/llm_client.py bằng mock (hoàn toàn không gọi mạng/AI thật).
Kiểm tra:
- Cache hit không gọi mạng
- Tự động retry khi gặp lỗi 429
- Chuyển sang fallback model khi model chính không tồn tại
- Bóc tách và parse cấu trúc JSON từ markdown code block
- Retry đúng 1 lần khi parse JSON bị lỗi
- Báo lỗi tiếng Việt rõ ràng khi thiếu API key
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ai_analysis.llm_client import (
    call_llm,
    call_llm_json,
    get_usage,
    reset_usage,
)


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Cấu hình môi trường mock test: API key giả lập, cache tạm và tắt time.sleep."""
    cache_dir = tmp_path / "test_ai_cache"
    monkeypatch.setattr("config.settings.CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("AI_API_KEY", "test_mock_api_key_12345")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3-flash-preview")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "gemini-flash-latest")
    monkeypatch.setattr("time.sleep", lambda _: None)
    reset_usage()


def test_missing_api_key_raises_vietnamese_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm tra báo lỗi tiếng Việt rõ ràng khi không có AI_API_KEY."""
    monkeypatch.setenv("AI_API_KEY", "")
    with pytest.raises(ValueError) as excinfo:
        call_llm("Xin chào", use_cache=False)
    assert "Thiếu API key cho mô hình AI" in str(excinfo.value)


def test_cache_hit_does_not_call_network() -> None:
    """Kiểm tra lần gọi thứ hai trúng cache thì không gọi ra mạng."""
    mock_response = MagicMock()
    mock_response.text = "Chào bạn! Tôi là trợ lý AI."
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 15

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("ai_analysis.llm_client._get_client", return_value=mock_client):
        # Lần 1: Gọi thật và lưu cache
        res1 = call_llm("Xin chào", system="System test", use_cache=True)
        assert res1 == "Chào bạn! Tôi là trợ lý AI."
        assert mock_client.models.generate_content.call_count == 1
        usage1 = get_usage()
        assert usage1["calls"] == 1
        assert usage1["cache_hits"] == 0
        assert usage1["input_tokens"] == 10
        assert usage1["output_tokens"] == 15

        # Lần 2: Trúng cache, không gọi lại generate_content
        res2 = call_llm("Xin chào", system="System test", use_cache=True)
        assert res2 == "Chào bạn! Tôi là trợ lý AI."
        assert mock_client.models.generate_content.call_count == 1  # Không tăng
        usage2 = get_usage()
        assert usage2["calls"] == 1
        assert usage2["cache_hits"] == 1


def test_retry_on_429() -> None:
    """Kiểm tra tự động retry tối đa 2 lần khi gặp lỗi 429 và thành công ở lần sau."""
    err_429 = Exception("429 Resource has been exhausted (e.g. check quota). Please retry after 2s.")
    mock_success_response = MagicMock()
    mock_success_response.text = "Thành công sau khi thử lại."
    mock_success_response.usage_metadata.prompt_token_count = 5
    mock_success_response.usage_metadata.candidates_token_count = 10

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [err_429, mock_success_response]

    with patch("ai_analysis.llm_client._get_client", return_value=mock_client):
        result = call_llm("Câu hỏi thử nghiệm 429", use_cache=False)
        assert result == "Thành công sau khi thử lại."
        assert mock_client.models.generate_content.call_count == 2


def test_fallback_model_on_model_not_found() -> None:
    """Kiểm tra khi model chính gặp lỗi không tồn tại (404) thì tự động chuyển sang fallback model."""
    err_404 = Exception("404 Model gemini-3-flash-preview is not found")
    mock_fallback_response = MagicMock()
    mock_fallback_response.text = "Kết quả từ model dự phòng."
    mock_fallback_response.usage_metadata = None

    mock_client = MagicMock()

    def generate_side_effect(model: str, contents: str, config: Any) -> Any:
        if model == "gemini-3-flash-preview":
            raise err_404
        return mock_fallback_response

    mock_client.models.generate_content.side_effect = generate_side_effect

    with patch("ai_analysis.llm_client._get_client", return_value=mock_client):
        result = call_llm("Test fallback", use_cache=False)
        assert result == "Kết quả từ model dự phòng."
        assert mock_client.models.generate_content.call_count == 2


def test_extract_and_parse_json() -> None:
    """Kiểm tra tự động bóc tách JSON khi AI bọc trong khối code markdown ```json ... ```."""
    mock_response = MagicMock()
    mock_response.text = '```json\n{\n  "relevance_score": 95,\n  "summary": "Nghiên cứu xuất sắc"\n}\n```'
    mock_response.usage_metadata = None

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("ai_analysis.llm_client._get_client", return_value=mock_client):
        data = call_llm_json("Phân tích bài báo", use_cache=False)
        assert isinstance(data, dict)
        assert data["relevance_score"] == 95
        assert data["summary"] == "Nghiên cứu xuất sắc"


def test_json_parse_retry_once() -> None:
    """Kiểm tra khi lần đầu trả về JSON lỗi cú pháp thì tự động gọi lại lần 2 để sửa lỗi."""
    mock_invalid_resp = MagicMock()
    mock_invalid_resp.text = '{"relevance_score": 90, summary: lỗi thiếu ngoặc kép'
    mock_invalid_resp.usage_metadata = None

    mock_valid_resp = MagicMock()
    mock_valid_resp.text = '{"relevance_score": 90, "summary": "Đã sửa cú pháp"}'
    mock_valid_resp.usage_metadata = None

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = [mock_invalid_resp, mock_valid_resp]

    with patch("ai_analysis.llm_client._get_client", return_value=mock_client):
        data = call_llm_json("Yêu cầu JSON", use_cache=False)
        assert isinstance(data, dict)
        assert data["summary"] == "Đã sửa cú pháp"
        assert mock_client.models.generate_content.call_count == 2
