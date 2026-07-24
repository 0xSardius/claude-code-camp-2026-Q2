"""Port of week1_baseline/ruby/05_agent_loop/lib/boukensha/backends/anthropic.rb --
adds tools= override on to_payload and parse_response (see
docs/plans/python_port/05_agent_loop)."""
from .base import Base


class Anthropic(Base):
    BASE_URL = "https://api.anthropic.com/v1/messages"
    MODELS = {
        "claude-haiku-4-5": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-haiku-4-5-20251001": {
            "context_window": 200_000,
            "cost_per_million": {"input": 1.0, "output": 5.0},
            "usage_unit": "tokens",
        },
        "claude-sonnet-4-6": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
        },
        "claude-sonnet-5": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 3.0, "output": 15.0},
            "usage_unit": "tokens",
        },
        "claude-opus-4-8": {
            "context_window": 1_000_000,
            "cost_per_million": {"input": 5.0, "output": 25.0},
            "usage_unit": "tokens",
        },
    }

    def __init__(self, *, api_key, model):
        super().__init__()
        self._api_key = api_key
        self._configure_model(model)

    # system is unused here -- Anthropic sends it as a separate top-level
    # payload field (see to_payload), not inline in the messages array.
    # Still accepted so every backend has the same to_messages(system,
    # messages) shape; PromptBuilder#to_messages delegates uniformly
    # without needing to special-case which backends need it inline.
    def to_messages(self, system, messages):
        result = []
        for msg in messages:
            if msg.role == "tool_result":
                result.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_use_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            else:
                result.append({"role": msg.role, "content": msg.content})
        return result

    def to_tools(self, tools):
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": tool.parameters,
                    "required": list(tool.parameters.keys()),
                },
            }
            for tool in tools.values()
        ]

    def to_payload(self, context, *, max_output_tokens=1024, tools=None):
        # tools if tools is not None else ... -- NOT `tools or ...`. An
        # explicit tools=[] (Agent's wrap-up call) must be honored as-is,
        # not treated as falsy and recomputed from context.tools.
        return {
            "model": self.model,
            "system": context.system,
            "max_tokens": max_output_tokens,
            "tools": self.to_tools(context.tools) if tools is None else tools,
            "messages": self.to_messages(context.system, context.messages),
        }

    def headers(self):
        return {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

    def url(self):
        return self.BASE_URL

    def parse_response(self, response):
        stop_reason = "tool_use" if response.get("stop_reason") == "tool_use" else "end_turn"
        return {"stop_reason": stop_reason, "content": response.get("content") or []}
