"""Port of week1_baseline/ruby/05_agent_loop/lib/boukensha/backends/gemini.rb --
adds tools= override on to_payload, parse_response, and private
_assistant_parts (the inverse of parse_response, used when replaying an
assistant turn into the next request -- see
docs/plans/python_port/05_agent_loop)."""
from .base import Base


class Gemini(Base):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS = {
        "gemini-3.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.5, "output": 9.0},
            "usage_unit": "tokens",
        },
        "gemini-3.1-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.25, "output": 1.5},
            "usage_unit": "tokens",
        },
        "gemini-2.5-pro": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 1.25, "output": 10.0},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.30, "output": 2.50},
            "usage_unit": "tokens",
        },
        "gemini-2.5-flash-lite": {
            "context_window": 1_048_576,
            "cost_per_million": {"input": 0.10, "output": 0.40},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key, model):
        super().__init__()
        self._api_key = api_key
        self._configure_model(model)

    # system is unused here -- Gemini sends it as a separate top-level
    # systemInstruction field (see to_payload), not inline in contents.
    # Still accepted so every backend has the same to_messages(system,
    # messages) shape; PromptBuilder#to_messages delegates uniformly
    # without needing to special-case which backends need it inline.
    def to_messages(self, system, messages):
        result = []
        for msg in messages:
            if msg.role == "assistant":
                result.append({"role": "model", "parts": self._assistant_parts(msg.content)})
            elif msg.role == "tool_result":
                result.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg.tool_use_id,
                                    "response": {"content": msg.content},
                                }
                            }
                        ],
                    }
                )
            else:
                result.append({"role": msg.role, "parts": [{"text": msg.content}]})
        return result

    def to_tools(self, tools):
        if not tools:
            return []

        return [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": {
                            "type": "object",
                            "properties": tool.parameters,
                            "required": list(tool.parameters.keys()),
                        },
                    }
                    for tool in tools.values()
                ]
            }
        ]

    def to_payload(self, context, *, max_output_tokens=1024, tools=None):
        return {
            "systemInstruction": {"parts": [{"text": context.system}]},
            "contents": self.to_messages(context.system, context.messages),
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }

    def headers(self):
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

    def url(self):
        return f"{self.BASE_URL}/{self.model}:generateContent"

    # Normalizes a Gemini generateContent response into the common shape.
    # Ruby's response.dig("candidates", 0, "content", "parts") safely
    # no-ops through any missing level of nesting; Python has no built-in
    # dig, translated with .get(...) or {}/or [] chaining instead of a
    # dedicated helper (same "not every Ruby line needs a literal Python
    # counterpart" reasoning as 02_the_registry's transform_keys gap).
    #
    # Gemini doesn't assign call ids, so the function name is reused as
    # the id (Gemini also matches functionResponse back to a call by name).
    def parse_response(self, response):
        candidates = response.get("candidates") or []
        first = candidates[0] if candidates else {}
        parts = (first.get("content") or {}).get("parts") or []

        content = []
        tool_used = False
        for part in parts:
            if part.get("functionCall"):
                fc = part["functionCall"]
                content.append(
                    {"type": "tool_use", "id": fc["name"], "name": fc["name"], "input": fc.get("args") or {}}
                )
                tool_used = True
            # Ruby: `elsif part["text"]` -- nil-only falsy, so an empty
            # string still passes. `is not None`, not a truthy check.
            elif part.get("text") is not None:
                content.append({"type": "text", "text": part["text"]})

        return {"stop_reason": "tool_use" if tool_used else "end_turn", "content": content}

    # Rebuilds Gemini "model" parts from normalized content blocks (the
    # inverse of parse_response).
    def _assistant_parts(self, content):
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        result = []
        for b in blocks:
            if b.get("type") == "tool_use":
                result.append({"functionCall": {"name": b["name"], "args": b["input"]}})
            else:
                result.append({"text": b["text"]})
        return result
