"""
🛠️ TOOL DEFINITIONS & EXECUTION BACKEND
Mã nguồn chứa danh sách Tool Schemas (JSON Schema) và Execution Layer phục vụ cho MCP Server.
"""

import json
from typing import Dict, Any

# ==============================================================================
# 1. KHAI BÁO TOOL SCHEMAS CHUẨN NATIVE JSON SCHEMA (TASK 1.2)
# ==============================================================================

TOOLS_SCHEMA = [
    {
        "name": "library_query",
        "description": "Tra cứu thông tin sách/tài liệu trong thư viện, bao gồm tên tài liệu, tác giả, vị trí lưu trữ và tình trạng mượn/trả.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Mã sách hoặc tài liệu cần tra cứu (ví dụ: 'TL001')."
                }
            },
            "required": ["document_id"]
        }
    },
    {
        "name": "renew_library_item",
        "description": "Gia hạn thời gian mượn sách hoặc tài liệu cho đúng người đang mượn.",
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Mã sách hoặc tài liệu cần gia hạn (ví dụ: 'TL002')."
                },
                "datetime_str": {
                    "type": "string",
                    "description": "Thời hạn mới sau khi gia hạn (ví dụ: '14:00 15/09/2026')."
                },
                "borrower_name": {
                    "type": "string",
                    "description": "Họ tên người đang mượn tài liệu."
                }
            },
            "required": ["document_id", "datetime_str", "borrower_name"]
        }
    }
]

# ==============================================================================
# 2. MÔ PHỎNG DỮ LIỆU & HÀM THỰC THI TOOL (EXECUTION LAYER)
# ==============================================================================

MOCK_DATABASE = {
    "TL001": {
        "title": "Lập trình Python cơ bản",
        "author": "Nguyễn Văn An",
        "category": "Công nghệ thông tin",
        "location": "Tầng 2 - Kệ CNTT-01",
        "status": "Có sẵn",
        "borrower_name": None,
        "due_date": None,
        "reserved_by": None
    },
    "TL002": {
        "title": "Trí tuệ nhân tạo hiện đại",
        "author": "Trần Minh Đức",
        "category": "Trí tuệ nhân tạo",
        "location": "Tầng 2 - Kệ AI-02",
        "status": "Đang được mượn",
        "borrower_name": "Nguyễn Minh Anh",
        "due_date": "14:00 15/09/2026",
        "reserved_by": None
    },
    "TL003": {
        "title": "Kỹ nghệ phần mềm",
        "author": "Lê Hoàng Nam",
        "category": "Kỹ thuật phần mềm",
        "location": "Tầng 3 - Kệ SE-01",
        "status": "Đang được mượn",
        "borrower_name": "Trần Thị Bình",
        "due_date": "09:00 14/09/2026",
        "reserved_by": "Phạm Gia Huy"
    }
}


def execute_library_query(document_id: str) -> str:
    """Thực thi tra cứu sách/tài liệu theo mã tài liệu."""
    normalized_id = document_id.strip().upper()
    document = MOCK_DATABASE.get(normalized_id)

    if document:
        return json.dumps({
            "status": "SUCCESS",
            "document_id": normalized_id,
            "data": document
        }, ensure_ascii=False)

    return json.dumps({
        "status": "NOT_FOUND",
        "message": f"Không tìm thấy sách hoặc tài liệu có mã '{document_id}'."
    }, ensure_ascii=False)


def execute_renew_library_item(
    document_id: str,
    datetime_str: str,
    borrower_name: str
) -> str:
    """Thực thi gia hạn tài liệu cho đúng người đang mượn."""
    normalized_id = document_id.strip().upper()
    normalized_borrower = borrower_name.strip()
    new_due_date = datetime_str.strip()
    document = MOCK_DATABASE.get(normalized_id)

    if not document:
        return json.dumps({
            "status": "NOT_FOUND",
            "message": f"Không tìm thấy sách hoặc tài liệu có mã '{document_id}'."
        }, ensure_ascii=False)

    if document["status"] != "Đang được mượn":
        return json.dumps({
            "status": "INVALID_STATUS",
            "message": f"Tài liệu '{normalized_id}' hiện không ở trạng thái đang được mượn."
        }, ensure_ascii=False)

    current_borrower = document.get("borrower_name") or ""
    if current_borrower.casefold() != normalized_borrower.casefold():
        return json.dumps({
            "status": "BORROWER_MISMATCH",
            "message": f"Tài liệu '{normalized_id}' không được mượn bởi '{borrower_name}'."
        }, ensure_ascii=False)

    if document.get("reserved_by"):
        return json.dumps({
            "status": "RENEWAL_REJECTED",
            "message": (
                f"Không thể gia hạn tài liệu '{normalized_id}' vì đã được "
                f"{document['reserved_by']} đặt trước."
            )
        }, ensure_ascii=False)

    if not new_due_date:
        return json.dumps({
            "status": "INVALID_DATETIME",
            "message": "Thời hạn gia hạn không được để trống."
        }, ensure_ascii=False)

    previous_due_date = document["due_date"]
    document["due_date"] = new_due_date

    return json.dumps({
        "status": "SUCCESS",
        "document_id": normalized_id,
        "title": document["title"],
        "borrower_name": current_borrower,
        "previous_due_date": previous_due_date,
        "new_due_date": new_due_date,
        "message": (
            f"Đã gia hạn tài liệu '{document['title']}' cho {current_borrower} "
            f"đến {new_due_date}."
        )
    }, ensure_ascii=False)


# Router gọi tool thực tế
TOOL_ROUTER = {
    "library_query": execute_library_query,
    "renew_library_item": execute_renew_library_item
}


def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Hàm trung chuyển thực thi tool."""
    if tool_name in TOOL_ROUTER:
        try:
            return TOOL_ROUTER[tool_name](**arguments)
        except Exception as e:
            return json.dumps({
                "status": "EXECUTION_ERROR",
                "error": str(e)
            }, ensure_ascii=False)

    return json.dumps({
        "status": "UNKNOWN_TOOL",
        "error": f"Tool '{tool_name}' không tồn tại!"
    }, ensure_ascii=False)