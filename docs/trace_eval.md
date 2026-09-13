# 📊 BÁO CÁO THU HOẠCH NGHIỆM THU BÀI LAB 3 (BƯỚC 3 — SUBMISSION ARTIFACT)

> **Họ và Tên Học viên:** Nguyễn Đình Anh Đức 
> **Mã Sinh Viên / Mã Học viên:** 2A202602856 
> **Chủ đề Lựa chọn:** Trợ lý Quản lý Thư viện & Tài liệu: Tra cứu vị trí sách, tình trạng mượn/trả và gia hạn tài liệu

---

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX (ĐÁNH GIÁ CHỦ ĐỀ)

| Tiêu chí Đánh giá | Mức độ (1 - 5) | Giải trình chi tiết lý do chọn điểm |
| :--- | :---: | :--- |
| **1. Multi-step Reasoning** | 4 / 5 | Bài toán yêu cầu chia nhỏ nhiều bước suy luận nối tiếp: xác định sách/tài liệu, tra cứu thông tin, kiểm tra trạng thái mượn/điều kiện gia hạn và tiến hành gia hạn |
| **2. Tool Interaction** | 5 / 5 | Hệ thống phải tương tác qua MCP Server để truy vấn danh mục thư viện, vị trí sách, trạng thái mượn/trả và thực hiện gia hạn |
| **3. Dynamic Decision** | 5 / 5 | Bước tiếp theo phụ thuộc rõ ràng vào kết quả trước: sách còn hay đang được mượn, tài khoản có quá hạn không, tài liệu có người đặt trước không và có đủ điều kiện gia hạn không |
| **4. Long Horizon Goal** | 3 / 5 | Hệ thống duy trì mục tiêu qua các bước tra cứu – kiểm tra – gia hạn, nhưng phần lớn yêu cầu hoàn thành trong một phiên ngắn |
| **TỔNG ĐIỂM AGENTIC FIT** | 17**/ 20** | *Nếu tổng điểm > 12/20: Bài toán rất phù hợp triển khai Agentic System.* |

---

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG (SAU KHI CHẠY TEST SUITE TRÊN API THẬT)

> ⚠️ **YÊU CẦU NGHIỆM THU:** Mở tệp `.env` điền `GEMINI_API_KEY` (hoặc `OPENAI_API_KEY`) để kết nối LLM thật trước khi thực thi `python src/app.py --all`. Bài nộp chỉ dùng Mock Offline Provider sẽ không đạt điểm nghiệm thực tế.

Dán 1 đoạn trích xuất log tiêu biểu từ file `docs/trace_waterfall.json` sinh ra từ phản hồi LLM API thật:

```json
[
  {
    "step": 1,
    "query": "Gia hạn tài liệu TL002 cho Nguyễn Minh Anh đến 14:00 29/09/2026.",
    "action_type": "TOOL_EXECUTION",
    "tool_name": "renew_library_item",
    "arguments": {
      "document_id": "TL002",
      "datetime_str": "14:00 29/09/2026",
      "borrower_name": "Nguyễn Minh Anh"
    },
    "observation": {
      "status": "SUCCESS",
      "document_id": "TL002",
      "title": "Trí tuệ nhân tạo hiện đại",
      "borrower_name": "Nguyễn Minh Anh",
      "previous_due_date": "14:00 15/09/2026",
      "new_due_date": "14:00 29/09/2026",
      "message": "Đã gia hạn tài liệu 'Trí tuệ nhân tạo hiện đại' cho Nguyễn Minh Anh đến 14:00 29/09/2026."
    },
    "latency_ms": 3888.1
  }
]
```

---

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

- [X] Đã điền API Key thật trong `.env` và xác nhận Agent chạy mượt mà trên LLM API thật (Gemini/OpenAI).
- **Tổng số Test Cases đã chạy thành công:** 5 / 5 test cases.
- **Số lượt gọi Tool qua MCP Server chính xác:** 4 lượt.
- **Kết quả đẩy Repo nộp bài:** [X] Đã Commit và Push mã nguồn thành công lên GitHub cá nhân.

---

> ✅ **HOÀN TẤT NỘP BÀI:** Sao chép đường link GitHub Repository cá nhân của bạn và dán vào ô nộp bài trên hệ thống LMS VLearn để hoàn tất Bài Lab 3!
