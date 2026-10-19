# Research Finder

Ứng dụng Streamlit hỗ trợ tìm kiếm và tổng hợp tài liệu nghiên cứu kinh tế từ các nguồn học thuật mở.

## Kế hoạch phát triển theo thứ tự

1. **models**: Khuôn dữ liệu bài báo chuẩn (`models/paper.py`).
2. **utils**: Tiện ích hệ thống và bộ nhớ đệm trên đĩa (`utils/file_cache.py`).
3. **sources**: Tích hợp các nguồn học thuật mở (`sources/openalex.py`, `sources/semantic_scholar.py`).
4. **merge**: Gộp nguồn và khử trùng lặp (`merge/dedupe_rank.py`).
5. **selection**: Quản lý trạng thái lựa chọn và danh sách hiển thị (`selection/state.py`).
6. **export**: Xuất danh sách bài báo đã chọn ra file Excel (`export/excel_writer.py`).
7. **ui**: Giao diện hiển thị bài báo và điều khiển (`ui/paper_card.py`, `ui/load_more.py`).
8. **ai_analysis**: Tích hợp AI tiết kiệm chi phí (`ai_analysis/llm_client.py`, `ai_analysis/screener.py`, `ai_analysis/analyzer.py`).
9. **pipeline**: Điều phối luồng tìm kiếm, lọc và phân tích tổng thể (`pipeline/search_pipeline.py`).
10. **app**: Ghép nối hoàn thiện ứng dụng Streamlit (`app.py`).
