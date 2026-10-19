"""
Module xây dựng đề xuất lộ trình và các bước nghiên cứu khoa học (Research Roadmap Builder).
Đầu vào: Đề tài nghiên cứu, loại hình nghiên cứu (định lượng, định tính, SLR...), và danh sách bài báo tham chiếu.
Đầu ra: Cấu trúc lộ trình gồm tổng quan, sơ đồ Mermaid và danh sách các giai đoạn/bước kèm nhiệm vụ, sản phẩm đầu ra.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ai_analysis.llm_client import call_llm_json
from models.paper import Paper


ROADMAP_SYSTEM_PROMPT = """Bạn là chuyên gia phương pháp luận nghiên cứu khoa học kinh tế - xã hội hàng đầu (Research Methodology Specialist).
Nhiệm vụ của bạn là lập đề xuất lộ trình nghiên cứu chi tiết, khoa học, thực tế và khả thi cho một đề tài nghiên cứu cụ thể.

Lộ trình nghiên cứu cần được phân chia thành 4 đến 5 giai đoạn hợp lý (ví dụ: Tổng quan lý thuyết, Thiết kế phương pháp & Mẫu, Thu thập & Xử lý dữ liệu, Ước lượng mô hình/Phân tích, Viết báo cáo & Đóng góp học thuật).
Mỗi giai đoạn gồm 2-3 bước nghiên cứu cụ thể. Mỗi bước phải chỉ rõ:
- Tên bước (title)
- Nhiệm vụ cụ thể cần làm (tasks)
- Sản phẩm đầu ra cụ thể (deliverable)
- Công cụ hoặc phương pháp khuyến nghị (tools_tips)

Bạn PHẢI trả về duy nhất 1 đối tượng JSON chuẩn xác với cấu trúc sau:
{
  "topic": "Tên đề tài",
  "research_type": "Loại hình nghiên cứu",
  "overview": "Đoạn văn ngắn (3-4 câu) mô tả hướng tiếp cận tổng thể, tính cấp thiết và phương pháp trọng tâm đề xuất.",
  "research_questions": [
    "Câu hỏi nghiên cứu 1",
    "Câu hỏi nghiên cứu 2",
    "Câu hỏi nghiên cứu 3"
  ],
  "mermaid_code": "Mã Mermaid flowchart TD thể hiện luồng các giai đoạn và bước chính. Lưu ý bọc nhãn trong dấu ngoặc vuông và ngoặc kép: A[\\"Giai đoạn 1: ...\\"] --> B[\\"Giai đoạn 2: ...\\"]",
  "phases": [
    {
      "phase_id": "P1",
      "phase_name": "Giai đoạn 1: ...",
      "description": "Mô tả mục tiêu giai đoạn 1",
      "steps": [
        {
          "id": "step_1_1",
          "title": "Tên bước",
          "tasks": "Nhiệm vụ chi tiết",
          "deliverable": "Sản phẩm đầu ra",
          "tools_tips": "Công cụ/Gợi ý"
        }
      ]
    }
  ]
}
Chỉ xuất JSON hợp lệ, không kèm văn bản giải thích bên ngoài.
"""


def _sanitize_mermaid_code(code: str) -> str:
    """Đảm bảo cú pháp Mermaid hợp lệ, không chứa ký tự đặc biệt gây lỗi render."""
    if not code:
        return ""
    clean = code.strip()
    # Loại bỏ code block markdown nếu có
    if clean.startswith("```"):
        lines = clean.split("\n")
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            clean = "\n".join(lines[1:-1]).strip()
        elif "```" in clean:
            clean = clean.replace("```mermaid", "").replace("```", "").strip()

    # Đảm bảo có dòng khai báo flowchart TD hoặc graph TD
    if not (clean.startswith("graph ") or clean.startswith("flowchart ")):
        clean = "flowchart TD\n" + clean

    return clean


def _build_fallback_roadmap(topic: str, research_type: str) -> dict[str, Any]:
    """Tạo lộ trình mẫu học thuật chuẩn mực dự phòng khi không gọi được AI."""
    safe_topic = topic or "Nghiên cứu khoa học"
    mermaid = f"""flowchart TD
    classDef phaseNode fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
    classDef stepNode fill:#0f172a,stroke:#64748b,stroke-width:1px,color:#cbd5e1;

    P1["Giai đoạn 1: Tổng quan & Khung lý thuyết"]:::phaseNode
    P2["Giai đoạn 2: Thiết kế phương pháp & Dữ liệu"]:::phaseNode
    P3["Giai đoạn 3: Phân tích & Ước lượng mô hình"]:::phaseNode
    P4["Giai đoạn 4: Thảo luận kết quả & Hoàn thiện"]:::phaseNode

    P1 --> P2 --> P3 --> P4
"""

    return {
        "topic": safe_topic,
        "research_type": research_type,
        "overview": (
            f"Lộ trình nghiên cứu cho chủ đề '{safe_topic}' theo định hướng {research_type}. "
            "Kế hoạch bao gồm 4 giai đoạn chuẩn mực từ tổng quan tài liệu, thiết kế khung nghiên cứu, "
            "thu thập xử lý dữ liệu đến phân tích thực nghiệm và hoàn thiện báo cáo khoa học."
        ),
        "research_questions": [
            f"Thực trạng và các nhân tố cốt lõi tác động đến {safe_topic} là gì?",
            f"Mối quan hệ định lượng/định tính giữa các biến số chính trong mô hình {safe_topic} diễn ra như thế nào?",
            f"Các hàm ý chính sách và giải pháp thực tiễn rút ra từ nghiên cứu về {safe_topic} là gì?",
        ],
        "mermaid_code": mermaid,
        "phases": [
            {
                "phase_id": "P1",
                "phase_name": "Giai đoạn 1: Xác định đề tài & Tổng quan tài liệu",
                "description": "Làm rõ tính cấp thiết, khoảng trống nghiên cứu và xây dựng cơ sở lý luận",
                "steps": [
                    {
                        "id": "step_1_1",
                        "title": "Xác định câu hỏi nghiên cứu & Mục tiêu đề tài",
                        "tasks": "Làm rõ bối cảnh nghiên cứu, tính cấp thiết và xác định 2-3 câu hỏi nghiên cứu trọng tâm.",
                        "deliverable": "Đề cương sơ bộ (Research Proposal) & Mục tiêu nghiên cứu",
                        "tools_tips": "Research Finder, Zotero, Google Scholar",
                    },
                    {
                        "id": "step_1_2",
                        "title": "Tổng quan tài liệu & Xác định khoảng trống (Research Gap)",
                        "tasks": "Thu thập 30-50 bài báo uy tín, lập bảng ma trận tổng quan tài liệu (Literature Matrix) theo tác giả, phương pháp và kết luận.",
                        "deliverable": "Chương 1: Tổng quan tình hình nghiên cứu & Bảng ma trận 18 cột",
                        "tools_tips": "Xuất Excel từ Research Finder, VOSviewer",
                    },
                    {
                        "id": "step_1_3",
                        "title": "Xây dựng khung lý thuyết & Phát triển giả thuyết",
                        "tasks": "Lựa chọn các lý thuyết nền tảng (Base Theories) và đề xuất mô hình nghiên cứu cùng các giả thuyết kiểm định (H1, H2...).",
                        "deliverable": "Sơ đồ khung nghiên cứu (Conceptual Framework) & Danh mục giả thuyết",
                        "tools_tips": "Draw.io, Miro, Obsidian",
                    },
                ],
            },
            {
                "phase_id": "P2",
                "phase_name": "Giai đoạn 2: Thiết kế phương pháp & Chuẩn bị dữ liệu",
                "description": "Định hình mô hình toán/kinh tế lượng hoặc phương pháp thu thập dữ liệu",
                "steps": [
                    {
                        "id": "step_2_1",
                        "title": "Định nghĩa biến số & Đo lường",
                        "tasks": "Xác định biến phụ thuộc, biến độc lập, biến kiểm soát cùng thước đo định lượng và nguồn trích dẫn thang đo.",
                        "deliverable": "Bảng định nghĩa và đo lường biến số nghiên cứu",
                        "tools_tips": "Thang đo Likert (nếu khảo sát) hoặc Chỉ số báo cáo tài chính/vĩ mô",
                    },
                    {
                        "id": "step_2_2",
                        "title": "Thu thập dữ liệu & Làm sạch dữ liệu",
                        "tasks": "Thu thập dữ liệu thứ cấp (bảng, chuỗi thời gian) hoặc dữ liệu sơ cấp (khảo sát bảng hỏi), kiểm tra missing value và outliers.",
                        "deliverable": "Bộ dữ liệu nghiên cứu sạch (Clean Dataset) sẵn sàng phân tích",
                        "tools_tips": "Python / Pandas, Stata, SPSS, Excel",
                    },
                ],
            },
            {
                "phase_id": "P3",
                "phase_name": "Giai đoạn 3: Phân tích thực nghiệm & Ước lượng mô hình",
                "description": "Thực hiện phân tích định lượng, kiểm định giả thuyết và độ tin cậy",
                "steps": [
                    {
                        "id": "step_3_1",
                        "title": "Thống kê mô tả & Ma trận tương quan",
                        "tasks": "Tính toán các giá trị Mean, Std, Min, Max, Skewness, Kurtosis và ma trận hệ số tương quan Pearson/Spearman.",
                        "deliverable": "Bảng thống kê mô tả & Bảng kiểm định đa cộng tuyến (VIF)",
                        "tools_tips": "Stata, R, EViews, SPSS",
                    },
                    {
                        "id": "step_3_2",
                        "title": "Ước lượng mô hình chính & Kiểm định giả thuyết",
                        "tasks": "Chạy hồi quy theo mô hình đã chọn (OLS, FEM, REM, GMM hoặc PLS-SEM) và đối chiếu p-value để chấp nhận/bác bỏ giả thuyết.",
                        "deliverable": "Bảng kết quả hồi quy mô hình chính",
                        "tools_tips": "Stata xtreg/xtabond, SmartPLS 4, R plm",
                    },
                    {
                        "id": "step_3_3",
                        "title": "Kiểm định tính vững (Robustness Checks)",
                        "tasks": "Thay đổi thước đo biến, chia nhóm mẫu hoặc áp dụng phương pháp ước lượng thay thế để đảm bảo kết quả không phụ thuộc vào phương pháp.",
                        "deliverable": "Bảng kiểm định tính vững & Thảo luận độ nhạy",
                        "tools_tips": "Endogeneity test, 2SLS, GMM",
                    },
                ],
            },
            {
                "phase_id": "P4",
                "phase_name": "Giai đoạn 4: Thảo luận kết quả, Hàm ý & Hoàn thiện",
                "description": "Viết báo cáo học thuật, so sánh với các nghiên cứu trước và đề xuất chính sách",
                "steps": [
                    {
                        "id": "step_4_1",
                        "title": "Thảo luận kết quả & Đóng góp học thuật",
                        "tasks": "So sánh kết quả nghiên cứu với các công trình trên thế giới, giải thích sự đồng thuận hoặc khác biệt dựa trên bối cảnh thực tế.",
                        "deliverable": "Chương Thảo luận kết quả (Discussion & Academic Contributions)",
                        "tools_tips": "So sánh với danh sách bài báo đã tìm kiếm",
                    },
                    {
                        "id": "step_4_2",
                        "title": "Đề xuất hàm ý chính sách & Hạn chế đề tài",
                        "tasks": "Rút ra các gợi ý cụ thể cho nhà hoạch định chính sách hoặc doanh nghiệp; chỉ rõ hạn chế về mẫu và hướng nghiên cứu tương lai.",
                        "deliverable": "Chương Kết luận, Hàm ý chính sách & Kiến nghị",
                        "tools_tips": "Policy Brief format",
                    },
                    {
                        "id": "step_4_3",
                        "title": "Biên tập bản thảo & Trích dẫn chuẩn APA",
                        "tasks": "Định dạng toàn bộ bài báo/khóa luận theo chuẩn học thuật (APA 7th), kiểm tra đạo văn và chuẩn bị nộp bài.",
                        "deliverable": "Bản thảo hoàn chỉnh (Final Manuscript)",
                        "tools_tips": "Zotero, Turnitin, Overleaf/LaTeX hoặc MS Word",
                    },
                ],
            },
        ],
    }


def generate_research_roadmap(
    topic: str,
    research_type: str = "Định lượng (Quantitative)",
    papers: Optional[list[Paper]] = None,
    use_cache: bool = True,
) -> dict[str, Any]:
    """
    Tạo đề xuất lộ trình nghiên cứu thông minh bằng mô hình AI cho chủ đề cụ thể.

    Đầu vào:
        topic: Đề tài hoặc câu hỏi nghiên cứu của người dùng.
        research_type: Định hướng nghiên cứu (Định lượng, Định tính, Hỗn hợp, Tổng quan SLR).
        papers: Danh sách các bài báo liên quan đã tìm được (nếu có) để tham chiếu phương pháp.
        use_cache: Bật/tắt đọc kết quả từ bộ nhớ đệm.

    Đầu ra:
        dict chứa: topic, research_type, overview, research_questions, mermaid_code, phases (steps).
    """
    clean_topic = (topic or "").strip()
    if not clean_topic:
        return _build_fallback_roadmap("Chưa xác định đề tài", research_type)

    # Tổng hợp thông tin từ các bài báo đã có để làm giàu ngữ cảnh
    papers_context = ""
    if papers:
        methods_found = []
        for p in papers[:6]:
            m = getattr(p, "methodology", "")
            d = getattr(p, "data_source", "") or getattr(p, "sample", "")
            if m:
                methods_found.append(f"- Bài '{p.title}': Phương pháp: {m}; Dữ liệu: {d}")
        if methods_found:
            papers_context = (
                "\n\nDưới đây là phương pháp và nguồn dữ liệu từ một số tài liệu học thuật tiêu biểu đã tìm thấy về đề tài này:\n"
                + "\n".join(methods_found)
            )

    prompt = f"""Hãy xây dựng đề xuất lộ trình nghiên cứu khoa học chi tiết cho đề tài sau:
ĐỀ TÀI: "{clean_topic}"
ĐỊNH HƯỚNG PHƯƠNG PHÁP: {research_type}
{papers_context}

YÊU CẦU:
1. Phân chia từ 4 đến 5 giai đoạn logic, mạch lạc.
2. Mỗi giai đoạn gồm 2-3 bước nghiên cứu cụ thể, có ID duy nhất (ví dụ: step_1_1, step_1_2, ...).
3. Mỗi bước có 'title', 'tasks' (nhiệm vụ rõ ràng), 'deliverable' (sản phẩm đầu ra đo lường được), 'tools_tips' (phần mềm/công cụ gợi ý).
4. Viết đoạn mã 'mermaid_code' dạng flowchart TD mô tả các giai đoạn và liên kết logic giữa chúng.
5. Ngôn ngữ: Tiếng Việt chuẩn học thuật kinh tế/khoa học xã hội.
"""

    try:
        data = call_llm_json(
            prompt=prompt,
            system=ROADMAP_SYSTEM_PROMPT,
            max_output_tokens=3000,
            use_cache=use_cache,
        )

        if isinstance(data, dict) and data.get("phases"):
            # Chuẩn hóa mã mermaid
            if "mermaid_code" in data:
                data["mermaid_code"] = _sanitize_mermaid_code(data["mermaid_code"])
            data["topic"] = clean_topic
            data["research_type"] = research_type
            return data
    except Exception:
        # Nếu AI gặp lỗi (hết hạn mức, không có key, lỗi parse...), sử dụng fallback học thuật
        pass

    return _build_fallback_roadmap(clean_topic, research_type)
