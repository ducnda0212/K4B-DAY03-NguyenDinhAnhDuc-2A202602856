"""
🔌 MULTI-PROVIDER LLM ADAPTER (Google Gemini, OpenAI & Offline Mock)
Hỗ trợ Native Tool Calling và chuyển đổi linh hoạt qua biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
from typing import Dict, Any, List
from dotenv import load_dotenv

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho các LLM Provider hỗ trợ Native Tool Calling"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        raise NotImplementedError


class MockOfflineProvider(BaseLLMProvider):
    """Offline Mock Provider dùng để kiểm thử ReAct Loop không cần API Key."""

    def __init__(self):
        self.model_name = "Offline-Mock-Model-2026"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return (
            "[Mock Chatbot Response]: Tôi có thể giải đáp quy định thư viện chung, "
            "nhưng không thể truy cập dữ liệu tài liệu thời gian thực."
        )

    @staticmethod
    def _extract_document_id(prompt: str) -> str:
        import re

        match = re.search(r"\bTL\d+\b", prompt, flags=re.IGNORECASE)
        return match.group(0).upper() if match else ""

    @staticmethod
    def _extract_datetime(prompt: str) -> str:
        import re

        match = re.search(
            r"\b\d{1,2}:\d{2}\s+\d{1,2}/\d{1,2}/\d{4}\b",
            prompt
        )
        return match.group(0) if match else ""

    @staticmethod
    def _extract_borrower_name(prompt: str) -> str:
        known_borrowers = ["Nguyễn Minh Anh", "Trần Thị Bình"]
        prompt_casefold = prompt.casefold()

        for borrower in known_borrowers:
            if borrower.casefold() in prompt_casefold:
                return borrower
        return ""

    @staticmethod
    def _extract_last_observation(prompt: str) -> tuple[str, Dict[str, Any]]:
        tool_marker = "MCP_TOOL_USED:"
        observation_marker = "MCP_OBSERVATION_JSON:"

        if tool_marker not in prompt or observation_marker not in prompt:
            return "", {}

        tool_name = prompt.rsplit(tool_marker, 1)[1].splitlines()[0].strip()
        raw_observation = prompt.rsplit(observation_marker, 1)[1].splitlines()[0].strip()

        try:
            return tool_name, json.loads(raw_observation)
        except json.JSONDecodeError:
            return tool_name, {}

    @staticmethod
    def _format_query_result(observation: Dict[str, Any]) -> str:
        if observation.get("status") != "SUCCESS":
            return observation.get(
                "message",
                "Không thể tra cứu thông tin tài liệu được yêu cầu."
            )

        data = observation.get("data", {})
        borrower = data.get("borrower_name") or "Chưa có người mượn"
        due_date = data.get("due_date") or "Không có"
        reserved_by = data.get("reserved_by") or "Không có"

        return (
            f"Tài liệu {observation.get('document_id', '')} - "
            f"'{data.get('title', '')}', tác giả {data.get('author', '')}. "
            f"Vị trí: {data.get('location', '')}. "
            f"Trạng thái: {data.get('status', '')}. "
            f"Người mượn: {borrower}. Hạn trả: {due_date}. "
            f"Người đặt trước: {reserved_by}."
        )

    def generate_with_tools(
        self,
        prompt: str,
        tools_schema: List[Dict[str, Any]],
        system_prompt: str = ""
    ) -> Dict[str, Any]:
        prompt_lower = prompt.casefold()
        document_id = self._extract_document_id(prompt)
        datetime_str = self._extract_datetime(prompt)
        borrower_name = self._extract_borrower_name(prompt)
        previous_tool, observation = self._extract_last_observation(prompt)

        # Sau Observation, Mock Provider quyết định bước kế tiếp của ReAct Loop.
        if previous_tool:
            status = observation.get("status")

            if status != "SUCCESS":
                return {
                    "type": "text",
                    "content": observation.get(
                        "message",
                        f"Công cụ trả về trạng thái {status or 'UNKNOWN'}."
                    ),
                    "thought": "Observation cho biết thao tác không thành công; trả lời đúng lỗi từ Tool."
                }

            if previous_tool == "library_query" and "gia hạn" in prompt_lower:
                data = observation.get("data", {})
                current_borrower = data.get("borrower_name")

                if data.get("status") != "Đang được mượn":
                    return {
                        "type": "text",
                        "content": "Tài liệu hiện không được mượn nên không cần gia hạn.",
                        "thought": "Observation cho thấy tài liệu không ở trạng thái đang được mượn."
                    }

                if data.get("reserved_by"):
                    return {
                        "type": "text",
                        "content": (
                            "Không thể gia hạn vì tài liệu đã được "
                            f"{data['reserved_by']} đặt trước."
                        ),
                        "thought": "Observation cho thấy tài liệu đã có người đặt trước."
                    }

                if not datetime_str:
                    return {
                        "type": "text",
                        "content": "Vui lòng cung cấp thời hạn mới theo định dạng HH:MM DD/MM/YYYY.",
                        "thought": "Đã xác minh tài liệu nhưng còn thiếu thời hạn gia hạn mới."
                    }

                return {
                    "type": "tool_call",
                    "tool_name": "renew_library_item",
                    "arguments": {
                        "document_id": observation.get("document_id", document_id),
                        "datetime_str": datetime_str,
                        "borrower_name": current_borrower
                    },
                    "thought": "Đã xác minh tài liệu đủ điều kiện; tiếp tục gọi Tool gia hạn."
                }

            if previous_tool == "library_query":
                return {
                    "type": "text",
                    "content": self._format_query_result(observation),
                    "thought": "Đã có dữ liệu tra cứu từ MCP Server; tổng hợp Final Answer."
                }

            if previous_tool == "renew_library_item":
                return {
                    "type": "text",
                    "content": observation.get(
                        "message",
                        "Đã hoàn tất gia hạn tài liệu."
                    ),
                    "thought": "Tool gia hạn đã thành công; trả kết quả cho người dùng."
                }

        # Lượt đầu tiên: xác định intent và Tool cần gọi.
        if "gia hạn" in prompt_lower:
            if not document_id:
                return {
                    "type": "text",
                    "content": "Vui lòng cung cấp mã tài liệu cần gia hạn.",
                    "thought": "Yêu cầu gia hạn còn thiếu document_id."
                }

            if not datetime_str:
                return {
                    "type": "text",
                    "content": "Vui lòng cung cấp thời hạn mới theo định dạng HH:MM DD/MM/YYYY.",
                    "thought": "Yêu cầu gia hạn còn thiếu datetime_str."
                }

            # Nếu chưa có tên người mượn hoặc người dùng yêu cầu kiểm tra trước,
            # Agent tra cứu tài liệu rồi mới quyết định gia hạn.
            if not borrower_name or "kiểm tra" in prompt_lower or "tra cứu" in prompt_lower:
                return {
                    "type": "tool_call",
                    "tool_name": "library_query",
                    "arguments": {"document_id": document_id},
                    "thought": "Cần kiểm tra trạng thái và người mượn trước khi gia hạn."
                }

            return {
                "type": "tool_call",
                "tool_name": "renew_library_item",
                "arguments": {
                    "document_id": document_id,
                    "datetime_str": datetime_str,
                    "borrower_name": borrower_name
                },
                "thought": "Yêu cầu đã đủ thông tin; gọi Tool gia hạn tài liệu."
            }

        if document_id or any(
            keyword in prompt_lower
            for keyword in ["tra cứu", "vị trí", "tình trạng", "tài liệu"]
        ):
            if not document_id:
                return {
                    "type": "text",
                    "content": "Vui lòng cung cấp mã tài liệu cần tra cứu.",
                    "thought": "Yêu cầu tra cứu còn thiếu document_id."
                }

            return {
                "type": "tool_call",
                "tool_name": "library_query",
                "arguments": {"document_id": document_id},
                "thought": "Cần gọi Tool tra cứu để lấy dữ liệu thư viện thực tế."
            }

        return {
            "type": "text",
            "content": (
                "Tôi là Trợ lý Quản lý Thư viện và Tài liệu. Tôi có thể hỗ trợ "
                "tra cứu vị trí, tình trạng tài liệu và gia hạn thời gian mượn."
            ),
            "thought": "Đây là câu hỏi chung, có thể trả lời trực tiếp mà không gọi Tool."
        }

class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider (Native Tool Calling với Google GenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(model=self.model_name, contents=contents)
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            print("ℹ️ [Gemini Provider]: Chưa tìm thấy GEMINI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)
        
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            
            # Chuẩn hóa function declarations cho Gemini SDK
            function_declarations = []
            for tool in tools_schema:
                # Bỏ qua các tool schema chưa được định nghĩa hoàn chỉnh
                if not tool.get("name") or not tool.get("parameters"):
                    continue
                function_declarations.append({
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {})
                })

            config = types.GenerateContentConfig(
                system_instruction=system_prompt if system_prompt else None,
                tools=[{"function_declarations": function_declarations}] if function_declarations else None,
                temperature=0.2
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )

            # Kiểm tra xem Gemini có trả về Tool Call không
            if response.function_calls:
                call = response.function_calls[0]
                args = dict(call.args) if hasattr(call, 'args') and call.args else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.name,
                    "arguments": args,
                    "thought": f"Gemini quyết định gọi công cụ '{call.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": response.text or "",
                    "thought": "Gemini phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }

        except Exception as e:
            print(f"⚠️ [Gemini API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (Native Tool Calling với OpenAI SDK)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env! Đang sử dụng chế độ Mock."
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(model=self.model_name, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"

    def generate_with_tools(self, prompt: str, tools_schema: List[Dict[str, Any]], system_prompt: str = "") -> Dict[str, Any]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            print("ℹ️ [OpenAI Provider]: Chưa tìm thấy OPENAI_API_KEY hợp lệ. Tự động chuyển sang Mock Offline.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            tools = []
            for tool in tools_schema:
                if not tool.get("name"):
                    continue
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {})
                    }
                })

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                call = msg.tool_calls[0]
                args = json.loads(call.function.arguments) if call.function.arguments else {}
                return {
                    "type": "tool_call",
                    "tool_name": call.function.name,
                    "arguments": args,
                    "thought": f"OpenAI quyết định gọi công cụ '{call.function.name}' với tham số: {json.dumps(args, ensure_ascii=False)}"
                }
            else:
                return {
                    "type": "text",
                    "content": msg.content or "",
                    "thought": "OpenAI phản hồi trực tiếp bằng văn bản (không cần gọi công cụ)."
                }
        except Exception as e:
            print(f"⚠️ [OpenAI API Warning]: Không thể kết nối live API ({str(e)}). Tự động fallback về Mock.")
            return MockOfflineProvider().generate_with_tools(prompt, tools_schema, system_prompt)


def get_llm_provider() -> BaseLLMProvider:
    """Factory function khởi tạo Provider theo LLM_PROVIDER env variable"""
    provider_type = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    if provider_type == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if key and key != "your_gemini_api_key_here":
            return GeminiProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key != "your_openai_api_key_here":
            return OpenAIProvider()
        else:
            return MockOfflineProvider()
    elif provider_type == "mock":
        return MockOfflineProvider()
    else:
        return MockOfflineProvider()
