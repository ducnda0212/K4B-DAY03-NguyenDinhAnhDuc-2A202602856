"""Web dashboard for the VinUni Library ReAct Agent lab.

Run from the project root:
    python src/web_server.py
Then open http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import mimetypes
import os
import sys
import threading
import time
from contextlib import redirect_stdout
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
WEB_DIR = ROOT_DIR / "web"
TRACE_PATH = ROOT_DIR / "docs" / "trace_waterfall.json"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import load_test_cases, run_react_agent  # noqa: E402
from mcp_server import MCPAcademicServer  # noqa: E402
from prompts import CHATBOT_BASELINE_PROMPT, MAX_ITERATIONS  # noqa: E402
from providers import get_llm_provider  # noqa: E402
from tools import MOCK_DATABASE, TOOLS_SCHEMA  # noqa: E402

INITIAL_DATABASE = copy.deepcopy(MOCK_DATABASE)
STATE_LOCK = threading.RLock()
LATEST_TRACE: list[dict[str, Any]] = []


def _load_existing_trace() -> list[dict[str, Any]]:
    if not TRACE_PATH.exists():
        return []
    try:
        data = json.loads(TRACE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_trace(trace: list[dict[str, Any]]) -> None:
    global LATEST_TRACE
    LATEST_TRACE = trace
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.write_text(
        json.dumps(trace, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _reset_database() -> None:
    MOCK_DATABASE.clear()
    MOCK_DATABASE.update(copy.deepcopy(INITIAL_DATABASE))


def _provider_metadata(provider: Any) -> dict[str, Any]:
    provider_name = provider.__class__.__name__
    return {
        "name": provider_name,
        "model": getattr(provider, "model_name", "Unknown"),
        "mode": "offline" if provider_name == "MockOfflineProvider" else "live",
    }


def _last_answer(trace: list[dict[str, Any]]) -> str:
    for event in reversed(trace):
        if event.get("action_type") == "FINAL_ANSWER":
            return str(event.get("output", ""))
    return "Agent đã xử lý yêu cầu nhưng chưa tạo được câu trả lời cuối cùng."


def _run_agent(query: str, provider: Any, server: MCPAcademicServer) -> dict[str, Any]:
    started_at = time.perf_counter()
    terminal_output = io.StringIO()

    with STATE_LOCK, redirect_stdout(terminal_output):
        trace = run_react_agent(query, provider, server)
        _save_trace(trace)

    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    tool_calls = sum(
        1 for event in trace if event.get("action_type") == "TOOL_EXECUTION"
    )

    return {
        "answer": _last_answer(trace),
        "trace": trace,
        "tool_calls": tool_calls,
        "latency_ms": elapsed_ms,
        "terminal_output": terminal_output.getvalue(),
    }


def _run_baseline(query: str, provider: Any) -> dict[str, Any]:
    started_at = time.perf_counter()
    answer = provider.generate(query, system_prompt=CHATBOT_BASELINE_PROMPT)
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
    trace = [{
        "step": 1,
        "query": query,
        "action_type": "FINAL_ANSWER",
        "thought": "Chatbot Baseline trả lời trực tiếp và không có quyền gọi Tool.",
        "output": answer,
        "latency_ms": elapsed_ms,
    }]
    return {
        "answer": answer,
        "trace": trace,
        "tool_calls": 0,
        "latency_ms": elapsed_ms,
    }


def _test_case_passed(test_case: dict[str, Any], trace: list[dict[str, Any]]) -> bool:
    events = [event.get("action_type") for event in trace]
    tools = [
        event.get("tool_name")
        for event in trace
        if event.get("action_type") == "TOOL_EXECUTION"
    ]
    test_type = test_case.get("type")

    if test_type == "direct_query":
        return "FINAL_ANSWER" in events and not tools
    if test_type == "single_tool_query":
        return "library_query" in tools
    if test_type == "renewal_action":
        return "renew_library_item" in tools
    if test_type == "multi_step_reasoning":
        return "library_query" in tools or "renew_library_item" in tools
    if test_type == "edge_case_handling":
        return any(
            event.get("observation", {}).get("status") == "NOT_FOUND"
            for event in trace
        )
    return bool(trace)


class LabRequestHandler(BaseHTTPRequestHandler):
    server_version = "VinAILabUI/1.0"

    @property
    def lab_server(self) -> "LabHTTPServer":
        return self.server  # type: ignore[return-value]

    def log_message(self, format_string: str, *args: Any) -> None:
        sys.stdout.write(
            f"🌐 [{self.log_date_time_string()}] "
            f"{format_string % args}\n"
        )

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def _serve_static(self, request_path: str) -> None:
        relative_path = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        relative_path = unquote(relative_path)
        target = (WEB_DIR / relative_path).resolve()
        web_root = WEB_DIR.resolve()

        if web_root not in target.parents and target != web_root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type, _ = mimetypes.guess_type(str(target))
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Cache-Control",
            "no-cache" if target.name == "index.html" else "public, max-age=3600",
        )
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/api/status":
            provider_meta = _provider_metadata(self.lab_server.provider)
            self._send_json({
                "ok": True,
                "provider": provider_meta,
                "server": {
                    "name": self.lab_server.mcp_server.server_name,
                    "version": self.lab_server.mcp_server.version,
                },
                "tool_count": len(TOOLS_SCHEMA),
                "document_count": len(MOCK_DATABASE),
                "max_iterations": MAX_ITERATIONS,
            })
            return

        if path == "/api/library":
            with STATE_LOCK:
                documents = [
                    {"document_id": document_id, **copy.deepcopy(data)}
                    for document_id, data in MOCK_DATABASE.items()
                ]
            self._send_json({"documents": documents})
            return

        if path == "/api/tools":
            self._send_json({"tools": TOOLS_SCHEMA})
            return

        if path == "/api/tests":
            self._send_json({"tests": load_test_cases()})
            return

        if path == "/api/trace":
            self._send_json({"trace": LATEST_TRACE})
            return

        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        payload = self._read_json()

        if path == "/api/chat":
            query = str(payload.get("query", "")).strip()
            mode = str(payload.get("mode", "agent")).strip().casefold()

            if not query:
                self._send_json(
                    {"error": "Vui lòng nhập câu hỏi."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                if mode == "baseline":
                    result = _run_baseline(query, self.lab_server.provider)
                else:
                    result = _run_agent(
                        query,
                        self.lab_server.provider,
                        self.lab_server.mcp_server,
                    )
                self._send_json({"ok": True, "mode": mode, **result})
            except Exception as exc:  # pragma: no cover - defensive API boundary
                self._send_json(
                    {"error": f"Không thể xử lý yêu cầu: {exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if path == "/api/run-tests":
            results = []
            combined_trace: list[dict[str, Any]] = []
            tests = load_test_cases()

            try:
                for test_case in tests:
                    with STATE_LOCK:
                        _reset_database()
                    result = _run_agent(
                        str(test_case.get("question", "")),
                        self.lab_server.provider,
                        self.lab_server.mcp_server,
                    )
                    trace = result["trace"]
                    combined_trace.extend(trace)
                    results.append({
                        "id": test_case.get("id"),
                        "type": test_case.get("type"),
                        "complexity": test_case.get("complexity"),
                        "question": test_case.get("question"),
                        "expected_behavior": test_case.get("expected_behavior"),
                        "passed": _test_case_passed(test_case, trace),
                        "answer": result["answer"],
                        "tool_calls": result["tool_calls"],
                        "latency_ms": result["latency_ms"],
                        "trace": trace,
                    })

                with STATE_LOCK:
                    _reset_database()
                    _save_trace(combined_trace)

                passed = sum(1 for result in results if result["passed"])
                self._send_json({
                    "ok": True,
                    "passed": passed,
                    "total": len(results),
                    "results": results,
                    "trace_events": len(combined_trace),
                })
            except Exception as exc:  # pragma: no cover
                self._send_json(
                    {"error": f"Không thể chạy test suite: {exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        if path == "/api/reset":
            with STATE_LOCK:
                _reset_database()
                _save_trace([])
            self._send_json({"ok": True, "message": "Đã khôi phục dữ liệu mock."})
            return

        self._send_json({"error": "Endpoint không tồn tại."}, HTTPStatus.NOT_FOUND)


class LabHTTPServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int]):
        super().__init__(address, LabRequestHandler)
        self.provider = get_llm_provider()
        self.mcp_server = MCPAcademicServer()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VinUni Library Agent Lab UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser.parse_args()


def main() -> None:
    global LATEST_TRACE
    args = parse_args()
    LATEST_TRACE = _load_existing_trace()
    server = LabHTTPServer((args.host, args.port))
    provider = _provider_metadata(server.provider)

    print("=" * 64)
    print("📚 VINUNI LIBRARY AGENT LAB — WEB DASHBOARD")
    print("=" * 64)
    print(f"🌐 URL: http://{args.host}:{args.port}")
    print(f"🤖 Provider: {provider['name']} · {provider['model']}")
    print(f"🔌 MCP Server: {server.mcp_server.server_name}")
    print("⛔ Nhấn Ctrl+C để dừng server.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Đang dừng Web Dashboard...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()