"""Port of week1_baseline/ruby/12_context/lib/boukensha/backends/gemini.rb --
adds reasoning-block normalization (thought/thoughtSignature <-> "reasoning")
and a thinkingConfig payload field. MODELS table: the third model
(gemini-3.1-pro-preview-customtools) is commented out in Ruby's own
source -- ported as a comment here too, not silently dropped, since
_thinking_config's branch for it is still live code even with no active
MODELS entry to reach it (matches Ruby's own dead branch)."""
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
        # "gemini-3.1-pro-preview-customtools": {
        #     "context_window": 1_048_576,
        #     "cost_per_million": {"input": 2.0, "output": 12.0},
        #     "usage_unit": "tokens",
        # },
    }

    def __init__(self, *, api_key, model):
        super().__init__()
        self._api_key = api_key
        self._configure_model(model)

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
                            "required": tool.required_params(),
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
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "thinkingConfig": self._thinking_config(),
            },
        }

    def headers(self):
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }

    def url(self):
        return f"{self.BASE_URL}/{self.model}:generateContent"

    # Normalizes a Gemini generateContent response into the common shape.
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
                    {
                        "type": "tool_use",
                        "id": fc["name"],
                        "name": fc["name"],
                        "input": fc.get("args") or {},
                        "signature": part.get("thoughtSignature"),
                    }
                )
                tool_used = True
            elif part.get("thought"):
                content.append(
                    {"type": "reasoning", "text": str(part.get("text") or ""), "signature": part.get("thoughtSignature")}
                )
            elif part.get("text") is not None:
                content.append({"type": "text", "text": part["text"]})

        return {"stop_reason": "tool_use" if tool_used else "end_turn", "content": content}

    def _thinking_config(self):
        if self.model == "gemini-3.1-pro-preview-customtools":
            return {"thinkingLevel": "LOW"}  # full disable not supported on this model
        return {"thinkingBudget": 0}  # gemini-3.5-flash, gemini-3.1-flash-lite

    # Rebuilds Gemini "model" parts from normalized content blocks (the
    # inverse of parse_response). Text-only turns are stored as a bare
    # string, so wrap it back into a single text block before mapping.
    def _assistant_parts(self, content):
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content

        result = []
        for b in blocks:
            if b.get("type") == "tool_use":
                part = {"functionCall": {"name": b["name"], "args": b["input"]}}
                if b.get("signature"):
                    part["thoughtSignature"] = b["signature"]
                result.append(part)
            elif b.get("type") == "reasoning":
                part = {"text": str(b.get("text") or ""), "thought": True}
                if b.get("signature"):
                    part["thoughtSignature"] = b["signature"]
                result.append(part)
            else:
                result.append({"text": b["text"]})
        return result
