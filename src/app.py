"""
🚀 CORE AGENT APPLICATION (DAY 03: CHATBOT VS REACT AGENT)
Thực thi so sánh giữa Chatbot Baseline (Cấp 2) và ReAct Agent kết nối MCP Server (Cấp 3).
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from mcp_server import MCPAcademicServer
from prompts import (
    CHATBOT_BASELINE_PROMPT,
    REACT_AGENT_SYSTEM_PROMPT,
    MAX_ITERATIONS
)
from providers import get_llm_provider

load_dotenv()

def load_test_cases():
    """Tải danh sách 5 test cases từ config/test_cases.json hoặc config/test_cases.example.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    if not os.path.exists(config_path):
        example_path = os.path.join(base_dir, "config", "test_cases.example.json")
        if os.path.exists(example_path):
            print("⚠️ [CONFIG NOTICE]: Chưa thấy file 'config/test_cases.json'. Đang dùng mẫu 'config/test_cases.example.json'.")
            print("👉 Hãy chạy: copy config/test_cases.example.json config/test_cases.json và viết test cases theo đề tài của bạn!\n")
            config_path = example_path
        else:
            config_path = "test_cases.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_waterfall_trace(trace_data: list):
    """Ghi vết log Waterfall Trace Log ra file docs/trace_waterfall.json"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    trace_path = os.path.join(docs_dir, "trace_waterfall.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace_data, f, ensure_ascii=False, indent=2)
    print(f"📊 [OBSERVABILITY]: Đã lưu {len(trace_data)} sự kiện Waterfall Trace tại '{trace_path}'!")


def run_baseline_chatbot(user_query: str, provider):
    """Chạy Chatbot gốc (Cấp 2) không có công cụ gọi Tool"""
    print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print(f"🤖 Chatbot phản hồi:\n{response}")


def run_react_agent(user_query: str, provider, mcp_server: MCPAcademicServer) -> list:
    """
    [REACT AGENT LOOP] Thực thi vòng lặp Thought -> Action -> Observation với MCP Server
    Trả về danh sách trace log của phiên thực thi.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")
    
    step = 0
    trace_logs = []
    tools_list = mcp_server.list_tools()
    working_prompt = user_query
    
    while step < MAX_ITERATIONS:
        step += 1
        step_start_time = time.time()
        print(f"\n--- 🔄 Vòng lặp ReAct Loop (Step {step}/{MAX_ITERATIONS}) ---")
        
        # Gọi LLM với Native Tool Calling Specs
        llm_response = provider.generate_with_tools(working_prompt, tools_list, system_prompt=REACT_AGENT_SYSTEM_PROMPT)
        latency_ms = round((time.time() - step_start_time) * 1000, 2)
        
        thought = llm_response.get("thought", "Đang suy luận...")
        print(f"🧠 [Thought]: {thought}")
        
        # Trường hợp 1: LLM quyết định trả lời bằng văn bản trực tiếp
        if llm_response.get("type") == "text":
            final_content = llm_response.get("content", "")
            print(f"🏁 [Final Answer]: {final_content}")
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": final_content,
                "latency_ms": latency_ms
            })
            break
            
        # Trường hợp 2: LLM đề xuất gọi Tool (Action)
        elif llm_response.get("type") == "tool_call":
            tool_name = llm_response.get("tool_name")
            arguments = llm_response.get("arguments", {})
            
            print(f"🛠️ [Action Proposed]: {tool_name}({arguments})")
            
            # Thực thi Tool qua MCP Server
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            obs_data = mcp_result.get("result", {})
            
            if not obs_data:
                print(f"👁️ [Observation từ MCP Server]: {{}}")
                print(f"⚠️ [CHÚ Ý]: MCP Server trả về kết quả rỗng! Học viên cần hoàn thành TODO 2.1 trong 'src/mcp_server.py'.")
                final_answer = "Chưa thể trả lời chi tiết do chưa nhận được dữ liệu từ MCP Server (hãy hoàn thành TODO 2.1)."
            else:
                obs_str = json.dumps(obs_data, ensure_ascii=False)
                print(f"👁️ [Observation từ MCP Server]: {obs_str}")
                
                # Tổng hợp Final Answer từ kết quả Observation thực tế
                if obs_data.get("status") == "SUCCESS":
                    # Kết quả từ tool library_query
                    if "data" in obs_data:
                        document = obs_data["data"]
                        borrower_name = document.get("borrower_name") or "Chưa có người mượn"
                        due_date = document.get("due_date") or "Không có"
                        reserved_by = document.get("reserved_by") or "Không có"

                        final_answer = (
                            f"Kết quả tra cứu tài liệu {obs_data.get('document_id', '')}: "
                            f"'{document.get('title', '')}', "
                            f"tác giả {document.get('author', '')}. "
                            f"Thể loại: {document.get('category', '')}. "
                            f"Vị trí: {document.get('location', '')}. "
                            f"Trạng thái: {document.get('status', '')}. "
                            f"Người mượn: {borrower_name}. "
                            f"Hạn trả: {due_date}. "
                            f"Người đặt trước: {reserved_by}."
                        )

                    # Kết quả từ tool renew_library_item
                    elif "message" in obs_data:
                        final_answer = obs_data["message"]
                    else:
                        final_answer = (
                            "Đã hoàn tất xử lý qua MCP Server: "
                            f"{json.dumps(obs_data, ensure_ascii=False)}"
                        )

                elif obs_data.get("status") == "NOT_FOUND":
                    final_answer = obs_data.get(
                        "message",
                        "Không tìm thấy sách hoặc tài liệu được yêu cầu."
                    )

                elif obs_data.get("status") in {
                    "INVALID_STATUS",
                    "BORROWER_MISMATCH",
                    "RENEWAL_REJECTED",
                    "INVALID_DATETIME"
                }:
                    final_answer = obs_data.get(
                        "message",
                        "Không thể thực hiện yêu cầu gia hạn tài liệu."
                    )

                else:
                    final_answer = (
                        "Phản hồi từ công cụ: "
                        f"{json.dumps(obs_data, ensure_ascii=False)}"
                    )
            trace_logs.append({
                "step": step,
                "query": user_query,
                "action_type": "TOOL_EXECUTION",
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": obs_data,
                "latency_ms": latency_ms
            })
            
            # Với yêu cầu "kiểm tra rồi gia hạn", nạp Observation của
            # library_query vào vòng lặp tiếp theo để Agent gọi renew_library_item.
            if tool_name == "library_query" and "gia hạn" in user_query.casefold():
                working_prompt = (
                    f"YÊU CẦU GỐC CỦA NGƯỜI DÙNG:\n{user_query}\n\n"
                    f"MCP_TOOL_USED: {tool_name}\n"
                    f"MCP_OBSERVATION_JSON: "
                    f"{json.dumps(obs_data, ensure_ascii=False)}\n\n"
                    "Dựa trên Observation, hãy gọi Tool tiếp theo nếu đủ điều kiện; "
                    "nếu không, hãy trả lời rõ lý do không thể gia hạn."
                )
                print("🔄 [ReAct Continue]: Nạp Observation để quyết định bước gia hạn tiếp theo.")
                continue

            # Kết thúc vòng lặp sau khi hoàn tất Observation và xuất Final Answer
            print(f"🧠 [Thought]: Đã nhận được dữ liệu từ MCP Server. Tổng hợp kết quả phản hồi.")
            print(f"🏁 [Final Answer]: {final_answer}")
            
            trace_logs.append({
                "step": step + 1,
                "query": user_query,
                "action_type": "FINAL_ANSWER",
                "thought": "Tổng hợp kết quả từ MCP Server thành công.",
                "output": final_answer,
                "latency_ms": 10.0
            })
            break

    return trace_logs


if __name__ == "__main__":
    print("==========================================================")
    print("🏫 VINUNI AI COURSE - DAY 03 LAB: CHATBOT VS REACT AGENT")
    print("==========================================================")
    
    provider = get_llm_provider()
    mcp_server = MCPAcademicServer()
    
    print(f"🔌 LLM Provider: {provider.__class__.__name__}")
    print(f"🌐 MCP Server: {mcp_server.server_name}\n")
    
    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases thử nghiệm.\n")

    if "--interactive" in sys.argv:
        print("🎮 [INTERACTIVE MODE] Trò chuyện với ReAct Agent thư viện:")
        print("💡 Gợi ý:")
        print("   - Tra cứu: 'Hãy tra cứu vị trí và tình trạng tài liệu TL001.'")
        print(
            "   - Gia hạn: 'Gia hạn TL002 cho Nguyễn Đình Anh Đức đến "
            "29/09/2026.'"
        )
        print(
            "   - Đa bước: 'Kiểm tra TL002 rồi gia hạn đến "
            "29/09/2026 nếu hợp lệ.'"
        )
        print("   - Gõ 'exit' hoặc 'quit' để kết thúc.\n")

        while True:
            try:
                user_input = input("👤 Người dùng hỏi: ").strip()
                if not user_input or user_input.casefold() in ["exit", "quit"]:
                    print("👋 Tạm biệt! Kết thúc phiên trò chuyện.")
                    break

                logs = run_react_agent(user_input, provider, mcp_server)
                save_waterfall_trace(logs)
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Đã thoát phiên tương tác.")
                break

    elif "--all" in sys.argv:
        print("🚀 [TEST SUITE MODE] Kiểm tra toàn bộ Test Cases:")
        completed_count = 0
        todo_count = 0
        all_traces = []

        for test_case in tests:
            print("\n==================================================")
            print(
                f"🧪 [{test_case['id']}] Loại test: {test_case['type']} "
                f"(Độ phức tạp: {test_case['complexity']})"
            )
            print(f"📌 Kỳ vọng: {test_case['expected_behavior']}")

            if test_case["question"].strip().startswith("TODO"):
                print("⏸️ [CHƯA KÍCH HOẠT - ĐANG LÀ TODO]")
                print(f"   {test_case['question']}")
                todo_count += 1
                continue

            logs = run_react_agent(
                test_case["question"],
                provider,
                mcp_server
            )
            all_traces.extend(logs)
            completed_count += 1

        print("\n==================================================")
        print(
            f"📊 [KẾT QUẢ TEST SUITE]: Đã thực thi "
            f"{completed_count}/{len(tests)} Test Cases | "
            f"{todo_count} Test Cases đang TODO"
        )

        if all_traces:
            save_waterfall_trace(all_traces)

        print("💡 Chạy tương tác bằng: python src/app.py --interactive")

    else:
        print("ℹ️ HƯỚNG DẪN SỬ DỤNG:")
        print("  1. Chat trực tiếp:          python src/app.py --interactive")
        print("  2. Chạy toàn bộ test:       python src/app.py --all\n")

        sample_query = tests[1]["question"]
        print("--- 🏁 DEMO TEST TRA CỨU TÀI LIỆU ---")
        logs = run_react_agent(sample_query, provider, mcp_server)
        save_waterfall_trace(logs)